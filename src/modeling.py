from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

import geopandas as gpd
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    BUSINESS_FEATURE_COLUMNS,
    DOCS_DIR,
    PEDAGOGICAL_CLUSTER_COUNT,
    PEDAGOGICAL_TARGET_COLUMN,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    TABLES_DIR,
)
from src.data_loader import (
    download_pedagogical_datasets,
    load_dataset,
    load_green_spaces_for_arrondissements,
    load_population_for_arrondissements,
    parse_overpass_lines,
    parse_overpass_points,
)
from src.preprocessing import (
    build_arrondissement_boundaries_from_iris,
    build_master_arrondissements,
)


PROCESSED_MASTER_CSV = PROCESSED_DATA_DIR / "master_arrondissements.csv"
PROCESSED_MASTER_GEOJSON = PROCESSED_DATA_DIR / "master_arrondissements.geojson"
REGRESSION_COLUMNS = BUSINESS_FEATURE_COLUMNS + ["cl_2", "cl_3"]


def _display_text(value: Any) -> str:
    """Return a display-safe string for markdown exports."""
    if pd.isna(value):
        return ""
    return str(value)


def load_master_arrondissements(csv_path: Path | None = None) -> pd.DataFrame:
    """Load the arrondissement-level master table from disk."""
    source_path = csv_path or PROCESSED_MASTER_CSV
    master_df = pd.read_csv(source_path, dtype={"arrondissement_code": "string"})
    master_df["arrondissement_code"] = master_df["arrondissement_code"].str.zfill(2)
    return master_df


def fit_arrondissement_kmeans(
    X_raw: pd.DataFrame,
    n_clusters: int = PEDAGOGICAL_CLUSTER_COUNT,
) -> tuple[pd.Series, pd.DataFrame]:
    """Fit KMeans on standardized business features and return labels plus raw cluster profiles."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    kmeans = KMeans(
        n_clusters=n_clusters,
        n_init=20,
        random_state=42,
    )
    cluster_labels = pd.Series(
        kmeans.fit_predict(X_scaled),
        index=X_raw.index,
        name="cluster_label",
    )

    cluster_profiles = X_raw.copy()
    cluster_profiles["cluster_label"] = cluster_labels
    summary = (
        cluster_profiles.groupby("cluster_label", as_index=False)[BUSINESS_FEATURE_COLUMNS]
        .mean()
    )
    cluster_sizes = cluster_profiles.groupby("cluster_label").size().rename("cluster_size").reset_index()
    summary = summary.merge(cluster_sizes, on="cluster_label", how="left")
    return cluster_labels, summary


def build_cluster_dummies(cluster_labels: pd.Series) -> pd.DataFrame:
    """One-hot encode cluster labels with drop_first=True to obtain cl_2 and cl_3."""
    raw_labels = pd.Series(cluster_labels, index=cluster_labels.index, name="cluster_label").astype(int)
    sorted_labels = sorted(raw_labels.unique().tolist())
    pedagogical_labels = raw_labels.map({label: idx + 1 for idx, label in enumerate(sorted_labels)})
    pedagogical_df = pd.DataFrame({"cluster_number": pedagogical_labels.astype(int)})

    try:
        encoder = OneHotEncoder(drop="first", sparse_output=False, dtype=int)
    except TypeError:  # pragma: no cover - compatibility fallback
        encoder = OneHotEncoder(drop="first", sparse=False, dtype=int)

    encoded = encoder.fit_transform(pedagogical_df[["cluster_number"]])
    output_columns = [f"cl_{value}" for value in sorted(pedagogical_df["cluster_number"].unique())[1:]]
    dummies = pd.DataFrame(encoded, columns=output_columns, index=cluster_labels.index)

    for required_column in ["cl_2", "cl_3"]:
        if required_column not in dummies.columns:
            dummies[required_column] = 0

    return dummies[["cl_2", "cl_3"]].astype(int)


def fit_multiple_linear_regression(X_reg: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
    """Fit the pedagogical multiple linear regression and compute in-sample diagnostics."""
    model = LinearRegression()
    model.fit(X_reg, y)

    predictions = pd.Series(model.predict(X_reg), index=X_reg.index, name="y_predicted")
    residuals = y - predictions
    n_rows = len(X_reg)
    n_features = X_reg.shape[1]
    r2_value = r2_score(y, predictions)
    adjusted_r2 = 1 - (1 - r2_value) * (n_rows - 1) / (n_rows - n_features - 1)

    coefficient_df = pd.DataFrame(
        {
            "term": ["Intercept"] + list(X_reg.columns),
            "coefficient": [float(model.intercept_)] + [float(value) for value in model.coef_],
        }
    )
    metrics = {
        "r2": float(r2_value),
        "adjusted_r2": float(adjusted_r2),
        "rmse": float(mean_squared_error(y, predictions) ** 0.5),
        "mae": float(mean_absolute_error(y, predictions)),
        "n_rows": int(n_rows),
        "n_features": int(n_features),
    }

    return {
        "model": model,
        "predictions": predictions,
        "residuals": residuals,
        "coefficients": coefficient_df,
        "metrics": metrics,
    }


def evaluate_linear_regression_loocv(X_reg: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    """Evaluate the linear regression with Leave-One-Out cross-validation."""
    loo = LeaveOneOut()
    model = LinearRegression()
    loocv_predictions = pd.Series(
        cross_val_predict(model, X_reg, y, cv=loo),
        index=X_reg.index,
        name="y_predicted_loocv",
    )
    return {
        "loocv_rmse": float(mean_squared_error(y, loocv_predictions) ** 0.5),
        "loocv_mae": float(mean_absolute_error(y, loocv_predictions)),
    }


def build_pedagogical_master_table(force_download: bool = False) -> gpd.GeoDataFrame:
    """Download missing sources, aggregate them at arrondissement level, and return the master table."""
    download_pedagogical_datasets(force=force_download)

    iris_gdf = load_dataset("iris_contours")
    bins_gdf = parse_overpass_points(RAW_DATA_DIR / "street_bins_osm_arr.json")
    commerce_gdf = parse_overpass_points(RAW_DATA_DIR / "commerce_restaurants_osm.json")
    transport_gdf = parse_overpass_points(RAW_DATA_DIR / "transport_stations_osm.json")
    roads_gdf = parse_overpass_lines(RAW_DATA_DIR / "roads_osm.json")
    population_df = load_population_for_arrondissements(RAW_DATA_DIR / "iris_population_2022.csv.zip")
    green_gdf = load_green_spaces_for_arrondissements(RAW_DATA_DIR / "green_spaces.csv")

    arr_gdf = build_arrondissement_boundaries_from_iris(iris_gdf)
    master_gdf = build_master_arrondissements(
        arr_gdf=arr_gdf,
        bins_gdf=bins_gdf,
        population_df=population_df,
        commerce_gdf=commerce_gdf,
        transport_gdf=transport_gdf,
        green_gdf=green_gdf,
        roads_gdf=roads_gdf,
    )
    return master_gdf


def _build_equation_string(coefficients_df: pd.DataFrame) -> str:
    """Render a human-readable regression equation."""
    intercept = coefficients_df.loc[coefficients_df["term"].eq("Intercept"), "coefficient"].iloc[0]
    terms = [f"{intercept:.3f}"]
    for row in coefficients_df.loc[~coefficients_df["term"].eq("Intercept")].itertuples(index=False):
        sign = "+" if row.coefficient >= 0 else "-"
        terms.append(f"{sign} {abs(row.coefficient):.6f}*{row.term}")
    return "Y = " + " ".join(terms)


def write_modeling_report(
    master_df: pd.DataFrame,
    cluster_summary_df: pd.DataFrame,
    coefficients_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
) -> Path:
    """Write the pedagogical regression report in Markdown."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    metrics = dict(zip(metrics_df["metric"], metrics_df["value"]))
    equation = _build_equation_string(coefficients_df)

    report_lines = [
        "# Modeling Report",
        "",
        "Date d'execution : 2026-03-13",
        "",
        "## Cadrage pedagogique",
        "",
        "- Unite d'analyse : arrondissement (20 observations)",
        f"- Variable cible Y : `{PEDAGOGICAL_TARGET_COLUMN}` = nombre brut de corbeilles OSM par arrondissement",
        "- Variables explicatives : X1 population, X2 commerces/restaurants, X3 stations de transport, X4 superficie d'espaces verts, X5 longueur de routes",
        "- Etape 2 : KMeans avec K=3",
        "- Etape 3 : One-Hot Encoding avec `drop_first=True` pour produire `cl_2` et `cl_3`",
        "- Etape 4 : LinearRegression",
        "",
        "## Variables du modele",
        "",
        "| Colonne | Definition |",
        "| --- | --- |",
        "| `x1_population` | Population INSEE totale par arrondissement |",
        "| `x2_commerce_restaurant_count` | Comptage OSM des commerces/restaurants |",
        "| `x3_transport_station_count` | Comptage OSM des stations de transport |",
        "| `x4_green_area_m2` | Surface totale d'espaces verts en m2 |",
        "| `x5_road_length_km` | Longueur totale des routes OSM en km |",
        "| `cl_2`, `cl_3` | Variables indicatrices des clusters KMeans |",
        "",
        "## Clusters d'arrondissements",
        "",
    ]

    for row in cluster_summary_df.sort_values("cluster_label").itertuples(index=False):
        report_lines.append(
            f"- Cluster {row.cluster_label} : size={int(row.cluster_size)}, "
            f"X1={row.x1_population:.1f}, X2={row.x2_commerce_restaurant_count:.1f}, "
            f"X3={row.x3_transport_station_count:.1f}, X4={row.x4_green_area_m2:.1f}, "
            f"X5={row.x5_road_length_km:.3f}"
        )

    report_lines.extend(
        [
            "",
            "## Equation finale",
            "",
            "```text",
            equation,
            "```",
            "",
            "## Coefficients",
            "",
            "| Terme | Coefficient |",
            "| --- | ---: |",
        ]
    )
    for row in coefficients_df.itertuples(index=False):
        report_lines.append(f"| `{row.term}` | {row.coefficient:.6f} |")

    report_lines.extend(
        [
            "",
            "## Metriques",
            "",
            "| Metrique | Valeur |",
            "| --- | ---: |",
        ]
    )
    for row in metrics_df.itertuples(index=False):
        value = float(row.value)
        if row.metric in {"n_rows", "n_features"}:
            report_lines.append(f"| `{row.metric}` | {int(value)} |")
        else:
            report_lines.append(f"| `{row.metric}` | {value:.6f} |")

    report_lines.extend(
        [
            "",
            "## Classement prescriptif",
            "",
            "- Le score de priorite est `y_predicted - y_bin_count`.",
            "- Un score positif signifie qu'un arrondissement presente un deficit estime de corbeilles par rapport a son profil urbain.",
            "",
            "| Rang | Arrondissement | Observe | Predit | Priority Score | Cluster |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in ranking_df.itertuples(index=False):
        report_lines.append(
            f"| {int(row.priority_rank)} | {row.arrondissement_name} | {int(row.y_bin_count)} | "
            f"{row.y_predicted:.3f} | {row.priority_score:.3f} | {int(row.cluster_label)} |"
        )

    report_lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "Le pipeline primaire suit maintenant strictement la logique pedagogique attendue : 20 arrondissements, clustering KMeans, variables indicatrices, puis regression lineaire multiple.",
        ]
    )

    report_path = DOCS_DIR / "modeling_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return report_path


def run_pedagogical_regression_pipeline(force_download: bool = False) -> dict[str, pd.DataFrame | dict[str, Any]]:
    """Execute the full arrondissement pedagogical pipeline and export all official artifacts."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    master_gdf = build_pedagogical_master_table(force_download=force_download)
    feature_matrix_df = master_gdf[
        ["arrondissement_code", "arrondissement_name", PEDAGOGICAL_TARGET_COLUMN] + BUSINESS_FEATURE_COLUMNS
    ].copy()

    cluster_labels, cluster_summary_df = fit_arrondissement_kmeans(
        feature_matrix_df[BUSINESS_FEATURE_COLUMNS],
        n_clusters=PEDAGOGICAL_CLUSTER_COUNT,
    )
    cluster_dummies = build_cluster_dummies(cluster_labels)

    master_gdf["cluster_label"] = cluster_labels.astype(int)
    master_gdf = pd.concat([master_gdf, cluster_dummies], axis=1)
    master_gdf["cl_2"] = master_gdf["cl_2"].astype(int)
    master_gdf["cl_3"] = master_gdf["cl_3"].astype(int)

    X_reg = master_gdf[REGRESSION_COLUMNS].copy()
    y = master_gdf[PEDAGOGICAL_TARGET_COLUMN].astype(float)
    regression_results = fit_multiple_linear_regression(X_reg, y)
    loocv_metrics = evaluate_linear_regression_loocv(X_reg, y)

    master_gdf["y_predicted"] = regression_results["predictions"]
    master_gdf["residual"] = y - master_gdf["y_predicted"]
    master_gdf["priority_score"] = master_gdf["y_predicted"] - y

    predictions_df = master_gdf[
        [
            "arrondissement_code",
            "arrondissement_name",
            PEDAGOGICAL_TARGET_COLUMN,
            "y_predicted",
            "residual",
            "priority_score",
            "cluster_label",
            "cl_2",
            "cl_3",
        ]
    ].copy()
    ranking_df = predictions_df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    ranking_df.insert(0, "priority_rank", range(1, len(ranking_df) + 1))

    cluster_table_df = master_gdf[
        [
            "arrondissement_code",
            "arrondissement_name",
            "cluster_label",
            "cl_2",
            "cl_3",
        ]
    ].copy()

    coefficients_df = regression_results["coefficients"].copy()
    metrics_dict = regression_results["metrics"] | loocv_metrics
    metrics_df = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in metrics_dict.items()]
    )

    master_gdf.to_file(PROCESSED_MASTER_GEOJSON, driver="GeoJSON")
    master_gdf.drop(columns="geometry").to_csv(PROCESSED_MASTER_CSV, index=False, encoding="utf-8-sig")
    feature_matrix_df.to_csv(
        TABLES_DIR / "arrondissement_feature_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )
    cluster_table_df.to_csv(
        TABLES_DIR / "arrondissement_clusters.csv",
        index=False,
        encoding="utf-8-sig",
    )
    cluster_summary_df.to_csv(
        TABLES_DIR / "arrondissement_cluster_profiles.csv",
        index=False,
        encoding="utf-8-sig",
    )
    coefficients_df.to_csv(
        TABLES_DIR / "arrondissement_regression_coefficients.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metrics_df.to_csv(
        TABLES_DIR / "arrondissement_regression_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    predictions_df.to_csv(
        TABLES_DIR / "arrondissement_predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )
    ranking_df.to_csv(
        TABLES_DIR / "arrondissement_priority_ranking.csv",
        index=False,
        encoding="utf-8-sig",
    )

    report_path = write_modeling_report(
        master_df=master_gdf.drop(columns="geometry"),
        cluster_summary_df=cluster_summary_df,
        coefficients_df=coefficients_df,
        metrics_df=metrics_df,
        ranking_df=ranking_df,
    )

    summary = {
        "rows_total": int(len(master_gdf)),
        "cluster_count": PEDAGOGICAL_CLUSTER_COUNT,
        "report_path": str(report_path),
        "priority_top_arrondissement": ranking_df.iloc[0]["arrondissement_name"],
        "loocv_rmse": float(loocv_metrics["loocv_rmse"]),
        "loocv_mae": float(loocv_metrics["loocv_mae"]),
    }
    (TABLES_DIR / "pedagogical_model_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "master_arrondissements": master_gdf.drop(columns="geometry"),
        "feature_matrix": feature_matrix_df,
        "cluster_profiles": cluster_summary_df,
        "coefficients": coefficients_df,
        "metrics": metrics_df,
        "predictions": predictions_df,
        "priority_ranking": ranking_df,
        "summary": summary,
    }


if __name__ == "__main__":
    outputs = run_pedagogical_regression_pipeline()
    print(json.dumps(outputs["summary"], indent=2, ensure_ascii=False))
