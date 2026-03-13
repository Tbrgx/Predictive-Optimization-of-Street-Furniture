"""Primary orchestrator for the pedagogical arrondissement pipeline."""

from pathlib import Path

from src.build_map import build_arrondissement_priority_map
from src.modeling import run_pedagogical_regression_pipeline


def main() -> None:
    outputs = run_pedagogical_regression_pipeline()
    map_path = build_arrondissement_priority_map()
    project_root = Path(__file__).resolve().parent
    ranking_path = (project_root / "outputs/tables/arrondissement_priority_ranking.csv").resolve()

    print("Pedagogical regression pipeline completed.")
    print(f"Priority ranking: {ranking_path}")
    print(f"Priority map: {map_path}")


if __name__ == "__main__":
    main()
