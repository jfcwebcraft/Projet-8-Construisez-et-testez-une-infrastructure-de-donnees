-- int_releves_unifies.sql
-- Unification des relevés météo de toutes les sources dans un schéma commun.
--
-- Cette couche intermédiaire assure :
--   1. Un schéma de colonnes homogène quelle que soit la source
--   2. La normalisation de l'horodatage (tous en UTC)
--   3. La préparation à la jointure avec les dimensions

with infoclimat as (

    select
        _airbyte_raw_id                         as raw_id,
        id_station,
        date_heure_utc,
        temperature_c,

        point_rosee_c,
        humidite_pct,
        pression_hpa,
        vent_moyen_kmh,
        vent_rafales_kmh,
        vent_direction_deg::text                as vent_direction,  -- degrés → texte unifié
        precipitations_1h_mm,
        null::numeric(6,2)                      as taux_precipitation_mm,
        null::numeric(6,2)                      as cumul_precipitation_mm,
        visibilite_m,
        null::smallint                          as uv_index,
        null::integer                           as rayonnement_solaire_wm2,
        neige_sol_cm,
        nebulosite_octas,
        code_temps_omm,
        source
    from {{ ref('stg_infoclimat_releves') }}

),

wunderground as (

    select
        _airbyte_raw_id                         as raw_id,
        id_station,
        -- Conversion en UTC : Europe/Paris = UTC+2 en été, UTC+1 en hiver
        -- Les données couvrent octobre 2024 (heure d'été jusqu'au 27/10, puis hiver)
        case
            when date_heure_locale < '2024-10-27 03:00:00' then
                date_heure_locale - interval '2 hours'
            else
                date_heure_locale - interval '1 hour'
        end                                     as date_heure_utc,
        temperature_c,
        point_rosee_c,
        humidite_pct,
        pression_hpa,
        vent_moyen_kmh,
        vent_rafales_kmh,
        direction_vent_cardinal                 as vent_direction,
        null::numeric(6,2)                      as precipitations_1h_mm,
        taux_precipitation_mm,
        cumul_precipitation_mm,
        null::integer                           as visibilite_m,
        uv_index,
        rayonnement_solaire_wm2,
        null::numeric(6,1)                      as neige_sol_cm,
        null::smallint                          as nebulosite_octas,
        null::smallint                          as code_temps_omm,
        source
    from {{ ref('stg_wunderground_releves') }}

),

unifies as (
    select * from infoclimat
    union all
    select * from wunderground
)

select * from unifies
