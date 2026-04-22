import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

def create_static_map():
    geojson_path = Path("data/processed/master_arrondissements.geojson")
    output_path = Path("outputs/figures/priority_map_static.png")
    
    if not geojson_path.exists():
        print("GeoJSON not found.")
        return
        
    gdf = gpd.read_file(geojson_path)
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    # Plot using an appropriate colormap similar to the folium map
    gdf.plot(column="priority_score", cmap="coolwarm", legend=True, 
             legend_kwds={'label': "Priority Score (Predicted - Observed Bins)", 'orientation': "horizontal"},
             ax=ax, edgecolor="black", linewidth=0.5)
             
    # Add arrondissement names as text labels
    for idx, row in gdf.iterrows():
        # Get centroid safely
        geom = row.geometry
        if geom is not None and not geom.is_empty:
            centroid = geom.centroid
            ax.annotate(text=str(row["arrondissement_code"]), xy=(centroid.x, centroid.y),
                        horizontalalignment='center', fontsize=9, color='white', 
                        bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=1))
                        
    ax.set_axis_off()
    plt.title("Carte des Priorités (Arrondissements)", fontsize=16, fontweight="bold", color="#002D74")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Static map created at {output_path}")

if __name__ == "__main__":
    create_static_map()
