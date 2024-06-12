import pandas as pd

df = pd.read_csv('runways.csv', usecols=['Loc Id', 'Runway Id', 'ICAO Id'], low_memory=False)

# Create a search function
def search_runways(df, identifier):
    result_iata = df.loc[df['Loc Id'] == identifier]
    result_icao = df.loc[df['ICAO Id'] == identifier]
    
    result = pd.concat([result_iata, result_icao]).drop_duplicates()
    
    return result

def split_runway_directions(runway_ids):
    directions = []
    for runway_id in runway_ids:
        if isinstance(runway_id, str) and '/' in runway_id:
            directions.extend(runway_id.split('/'))
    return directions

runway_directions = df.groupby('Loc Id')['Runway Id'].unique().reset_index()

runway_directions['Runway Directions'] = runway_directions['Runway Id'].apply(split_runway_directions)
runway_directions.drop(columns=['Runway Id'], inplace=True)

def get_runway_directions(identifier):
    search_result = search_runways(df, identifier)
    if not search_result.empty:
        loc_id = search_result.iloc[0]['Loc Id']
        directions = runway_directions.loc[runway_directions['Loc Id'] == loc_id, 'Runway Directions'].values
        if len(directions) > 0:
            return directions[0]
    return []

iata_runway_directions = get_runway_directions('KEWB')
print("Runway Directions for 'KEWB':", iata_runway_directions)

icao_runway_directions = get_runway_directions('BOS')
print("Runway Directions for 'BOS':", icao_runway_directions)
