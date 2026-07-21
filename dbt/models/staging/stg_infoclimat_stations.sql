-- stg_infoclimat_stations.sql
-- Standardisation des métadonnées de stations InfoClimat.
-- Le connecteur Airbyte Destinations V2 (typing & deduping) livre déjà des
-- colonnes typées : ce modèle se limite au renommage et à un typage explicite.

with source as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        id_station,
        nom_station,
        latitude,
        longitude,
        altitude_m,
        type_station,
        licence,
        licence_source,
        licence_url,
        licence_metadonnees_url
    from {{ source('raw_airbyte', 'infoclimat_stations') }}

),

renamedcast as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,

        id_station,
        nom_station,
        latitude::numeric(9,6)      as latitude,
        longitude::numeric(9,6)     as longitude,
        altitude_m::integer         as altitude_m,
        type_station,
        licence,
        licence_source,
        licence_url,
        licence_metadonnees_url,

        'infoclimat'                as source

    from source

)

select * from renamedcast
