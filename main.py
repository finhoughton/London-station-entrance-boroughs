import geopandas as gpd
import os
import string

station_aliases = {
    "Edgware Road (Bakerloo)": "Edgware Road",
    "Edgware Road (Circle Line)": "Edgware Road",
    "Paddington (H&C Line)": "Paddington",
    "Hammersmith (H&C Line)": "Hammersmith",
    "Hammersmith (Dist&Picc Line)": "Hammersmith",
    "Kensington Olympia": "Kensington (Olympia)",
    "BANK - DLR": "Bank-Monument",
    "Bank": "Bank-Monument",
    "Monument": "Bank-Monument",
    "TOWER GATEWAY - DLR": "Tower Gateway",
    "STRATFORD - DLR": "Stratford",
    "STRATFORD HIGH STREET - DLR": "Stratford",
    "CANARY WHARF - DLR": "Canary Wharf",
    "CANNING TOWN - DLR": "Canning Town",
    "West Croydon (Tramlink)": "West Croydon",
    "East Croydon (Tramlink)": "East Croydon",
    "Elmers End (Tramlink)": "Elmers End",
}


def find_entrances():
    stations_gdf = gpd.read_file("stations.json")[["name", "geometry"]]

    entrances_gfp = gpd.read_file("entrances.json")[["id", "name", "geometry"]]

    new_proj = stations_gdf.estimate_utm_crs() 
    stations_gdf = stations_gdf.to_crs(new_proj)
    entrances_gfp = entrances_gfp.to_crs(new_proj)

    entrances_proj = entrances_gfp.sort_values("id")
    unique_entrances = []

    for idx, row in entrances_proj.iterrows():
        too_close = False
        for kept in unique_entrances:
            if row.geometry.distance(kept.geometry) < 2:
                too_close = True
                break
        if not too_close:
            unique_entrances.append(row)

    entrances_dedup = gpd.GeoDataFrame(unique_entrances, crs=entrances_proj.crs)

    entrances_with_station = gpd.sjoin_nearest(
        entrances_dedup, stations_gdf[["name", "geometry"]], how="left", distance_col="dist_m"
    )
    entrances_with_station = entrances_with_station.rename(
        columns={"name_right": "station", "name_left": "entrance_name"}
    ).drop(columns=["index_right"])

    entrances_within_300m = entrances_with_station[entrances_with_station["dist_m"] <= 300].reset_index(drop=True)
    entrances_within_300m["station"] = entrances_within_300m["station"].replace(station_aliases).str.lower()

    os.makedirs("stations_geojson", exist_ok=True)
    for station, group in entrances_within_300m.to_crs(epsg=4326).groupby("station"):
        new_name = (''.join(c for c in station.lower() if c in string.ascii_lowercase or c == " ")).replace(" ", "_")
        filename = f"{new_name}.geojson"
        filepath = os.path.join("stations_geojson", filename)
        group[["id", "entrance_name", "dist_m", "geometry"]].to_file(filepath, driver="GeoJSON")

        print(f"Saved entrances for {station} at {filepath}")


def find_entrance_boroughs():
    boroughs_gdf = gpd.read_file("boroughs.json")[["short_name", "geometry"]]
    boroughs_gdf = boroughs_gdf.to_crs(epsg=4326)

    stations_gdfs = [
        (f.name.split(".")[0], gpd.read_file(f)[["geometry"]])
        for f in os.scandir("stations_geojson")
        if f.name.endswith(".geojson")
    ]

    stations_gdfs.sort(key=lambda x: len(x[1]))

    stations_multiple_boroughs = dict()

    for name, entrances_gdf in stations_gdfs:
        entrances_gdf = entrances_gdf.to_crs(boroughs_gdf.crs)
        joined = gpd.sjoin(entrances_gdf, boroughs_gdf, how="left", predicate="within")
        unique_boroughs = joined["short_name"].dropna().unique()

        if len(unique_boroughs) > 1:
            stations_multiple_boroughs[name] = unique_boroughs
            print(f"{name} spans {len(unique_boroughs)} boroughs: {unique_boroughs}")

if __name__ == "__main__":
    find_entrances()
    find_entrance_boroughs()
