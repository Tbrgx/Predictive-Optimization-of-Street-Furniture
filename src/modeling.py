from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    BUSINESS_FEATURE_COLUMNS,
    DOCS_DIR,
    FIGURES_DIR,
    MLP_ACTIVATION,
    MLP_ALPHA,
    MLP_HIDDEN_LAYER_SIZES,
    MLP_MAX_ITER,
    MLP_SOLVER,
    PEDAGOGICAL_CLUSTER_COUNT,
    PEDAGOGICAL_TARGET_COLUMN,
    PHASE2_FEATURE_COLUMNS,
    PHASE2_RANDOM_STATE,
    PHASE2_TARGET_COLUMN,
    PHASE2_TEST_SIZE,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    TABLES_DIR,
)
from src.data_loader import (
    download_pedagogical_datasets,
    load_dataset,
    load_green_spaces_for_arrondissements,
    load_population_for_arrondissements,
    load_schools_for_arrondissements,
    load_terrasses_for_arrondissements,
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
    terrasses_df = load_terrasses_for_arrondissements(RAW_DATA_DIR / "terrasses_autorisations.csv")
    schools_df = load_schools_for_arrondissements(
        colleges_path=RAW_DATA_DIR / "etablissements_colleges.csv",
        elementaires_path=RAW_DATA_DIR / "etablissements_elementaires.csv",
        maternelles_path=RAW_DATA_DIR / "etablissements_maternelles.csv",
    )

    arr_gdf = build_arrondissement_boundaries_from_iris(iris_gdf)
    master_gdf = build_master_arrondissements(
        arr_gdf=arr_gdf,
        bins_gdf=bins_gdf,
        population_df=population_df,
        commerce_gdf=commerce_gdf,
        transport_gdf=transport_gdf,
        green_gdf=green_gdf,
        roads_gdf=roads_gdf,
        terrasses_df=terrasses_df,
        schools_df=schools_df,
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
        f"Date d'execution : {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Cadrage pedagogique",
        "",
        "- Unite d'analyse : arrondissement (20 observations)",
        f"- Variable cible Y : `{PEDAGOGICAL_TARGET_COLUMN}` = nombre brut de corbeilles OSM par arrondissement",
        "- Variables explicatives : X1 population, X2 commerces/restaurants, X3 stations de transport, X4 superficie d'espaces verts, X5 longueur de routes, X6 surface de terrasses autorisees, X7 nombre d'etablissements scolaires",
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
        "| `x6_terrasse_surface_m2` | Surface totale des terrasses autorisees (longueur x largeur) en m2 |",
        "| `x7_school_count` | Nombre total d'etablissements scolaires (colleges + elementaires + maternelles) |",
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
            f"X5={row.x5_road_length_km:.3f}, X6={row.x6_terrasse_surface_m2:.1f}, "
            f"X7={row.x7_school_count:.1f}"
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


# ---------------------------------------------------------------------------
# Phase 2 – Neural Network pipeline
# ---------------------------------------------------------------------------


def create_feature_response_arrays(master_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Select X1..X7 features and y_bin_count target; validate types and NaN absence."""
    X = master_df[PHASE2_FEATURE_COLUMNS].copy()
    y = master_df[PHASE2_TARGET_COLUMN].copy()

    for col in PHASE2_FEATURE_COLUMNS:
        X[col] = pd.to_numeric(X[col], errors="raise")
    y = pd.to_numeric(y, errors="raise")

    if X.isna().any().any():
        raise ValueError(f"NaN detected in feature matrix: {X.isna().sum().to_dict()}")
    if y.isna().any():
        raise ValueError("NaN detected in target vector.")

    return X, y


def create_train_test_datasets(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = PHASE2_TEST_SIZE,
    random_state: int = PHASE2_RANDOM_STATE,
) -> dict[str, pd.DataFrame | pd.Series]:
    """Split X and y into train/test sets (no stratification – regression)."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
    }


def build_neural_network_pipeline() -> Pipeline:
    """Build a sklearn Pipeline: StandardScaler + MLPRegressor with fixed hyperparameters."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=MLP_HIDDEN_LAYER_SIZES,
            activation=MLP_ACTIVATION,
            solver=MLP_SOLVER,
            alpha=MLP_ALPHA,
            max_iter=MLP_MAX_ITER,
            random_state=PHASE2_RANDOM_STATE,
        )),
    ])


def evaluate_regression_predictions(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """Compute R2, RMSE, and MAE for a set of predictions."""
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


def _plot_y_vs_features(X: pd.DataFrame, y: pd.Series) -> None:
    """Save scatterplots of y vs each X feature."""
    feature_labels = [
        "X1 Population", "X2 Commerce/Restaurants", "X3 Transport Stations",
        "X4 Green Area (m2)", "X5 Road Length (km)",
        "X6 Terrasse Surface (m2)", "X7 School Count",
    ]
    n = len(PHASE2_FEATURE_COLUMNS)
    fig, axes = plt.subplots(1, n, figsize=(n * 4, 4))
    for ax, col, label in zip(axes, PHASE2_FEATURE_COLUMNS, feature_labels):
        ax.scatter(X[col], y, color="steelblue", edgecolors="white", linewidths=0.5)
        ax.set_xlabel(label, fontsize=9)
        ax.set_ylabel("Y (bin count)" if ax == axes[0] else "")
        ax.set_title(f"Y vs {label.split()[0]}", fontsize=10)
    fig.suptitle(f"Scatterplots: Y (bin count) vs X1..X{n}", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "y_vs_features_scatterplots.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_actual_vs_predicted(y_true: pd.Series, y_pred: np.ndarray) -> None:
    """Save actual vs predicted scatter for MLP."""
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y_true, y_pred, color="steelblue", edgecolors="white", linewidths=0.5)
    lims = [min(y_true.min(), y_pred.min()) * 0.9, max(y_true.max(), y_pred.max()) * 1.1]
    ax.plot(lims, lims, "r--", linewidth=1, label="Perfect fit")
    ax.set_xlabel("Actual Y (bin count)")
    ax.set_ylabel("Predicted Y (bin count)")
    ax.set_title("Neural Network: Actual vs Predicted")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "neural_network_actual_vs_predicted.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_residuals(y_true: pd.Series, y_pred: np.ndarray) -> None:
    """Save residuals vs predicted scatter for MLP."""
    residuals = y_true.values - y_pred
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(y_pred, residuals, color="steelblue", edgecolors="white", linewidths=0.5)
    ax.axhline(0, color="red", linestyle="--", linewidth=1)
    ax.set_xlabel("Predicted Y (bin count)")
    ax.set_ylabel("Residual")
    ax.set_title("Neural Network: Residuals vs Predicted")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "neural_network_residuals.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_phase2_neural_network_pipeline(
    csv_path: Path | None = None,
    force_download: bool = False,
) -> dict[str, Any]:
    """Full phase 2 pipeline: load data, split, train MLP, evaluate, export."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    if csv_path is None and not PROCESSED_MASTER_CSV.exists():
        build_pedagogical_master_table(force_download=force_download)

    master_df = load_master_arrondissements(csv_path)

    X, y = create_feature_response_arrays(master_df)

    datasets = create_train_test_datasets(X, y)
    X_train = datasets["X_train"]
    X_test = datasets["X_test"]
    y_train = datasets["y_train"]
    y_test = datasets["y_test"]

    pipeline = build_neural_network_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred_train = pipeline.predict(X_train)
    y_pred_test = pipeline.predict(X_test)

    train_metrics = {f"train_{k}": v for k, v in evaluate_regression_predictions(y_train, y_pred_train).items()}
    test_metrics = {f"test_{k}": v for k, v in evaluate_regression_predictions(y_test, y_pred_test).items()}

    loo = LeaveOneOut()
    y_pred_loocv = cross_val_predict(build_neural_network_pipeline(), X, y, cv=loo)
    loocv_metrics = {f"loocv_{k}": v for k, v in evaluate_regression_predictions(y, y_pred_loocv).items()}

    all_metrics = {**train_metrics, **test_metrics, **loocv_metrics}
    metrics_df = pd.DataFrame([{"metric": k, "value": v} for k, v in all_metrics.items()])

    y_pred_all = pipeline.predict(X)
    predictions_df = master_df[["arrondissement_code", "arrondissement_name"]].copy()
    predictions_df["y_observed"] = y.values
    predictions_df["y_predicted"] = y_pred_all
    predictions_df["residual"] = y.values - y_pred_all
    predictions_df["split"] = "train"
    predictions_df.loc[X_test.index, "split"] = "test"

    train_test_summary = pd.DataFrame([
        {"split": "train", "n_rows": len(X_train)},
        {"split": "test", "n_rows": len(X_test)},
    ])

    X.to_csv(TABLES_DIR / "phase2_feature_matrix.csv", index=False, encoding="utf-8-sig")
    y.to_csv(TABLES_DIR / "phase2_target_vector.csv", index=True, header=True, encoding="utf-8-sig")
    train_test_summary.to_csv(TABLES_DIR / "phase2_train_test_summary.csv", index=False, encoding="utf-8-sig")
    predictions_df.to_csv(TABLES_DIR / "neural_network_predictions.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(TABLES_DIR / "neural_network_metrics.csv", index=False, encoding="utf-8-sig")

    # Baseline linear regression comparison
    X_reg = master_df[BUSINESS_FEATURE_COLUMNS].astype(float)
    cluster_labels_bl, _ = fit_arrondissement_kmeans(X_reg)
    cluster_dummies_bl = build_cluster_dummies(cluster_labels_bl)
    X_reg_full = pd.concat([X_reg, cluster_dummies_bl], axis=1)
    baseline_results = fit_multiple_linear_regression(X_reg_full, y)
    loocv_baseline = evaluate_linear_regression_loocv(X_reg_full, y)
    baseline_metrics = {**baseline_results["metrics"], **loocv_baseline}
    pd.DataFrame(
        [{"metric": k, "value": v} for k, v in baseline_metrics.items()]
    ).to_csv(TABLES_DIR / "linear_regression_baseline_metrics.csv", index=False, encoding="utf-8-sig")

    # Figures
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_y_vs_features(X, y)
    _plot_actual_vs_predicted(y, pipeline.predict(X))
    _plot_residuals(y, pipeline.predict(X))

    return {
        "master_df": master_df,
        "X": X,
        "y": y,
        "datasets": datasets,
        "pipeline": pipeline,
        "predictions": predictions_df,
        "metrics": metrics_df,
        "all_metrics": all_metrics,
    }


if __name__ == "__main__":
    outputs = run_pedagogical_regression_pipeline()
    print(json.dumps(outputs["summary"], indent=2, ensure_ascii=False))
