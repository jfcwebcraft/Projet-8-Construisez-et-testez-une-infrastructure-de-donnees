-- dim_dates.sql
-- Dimension temporelle couvrant toutes les dates des relevés disponibles.
-- Permet aux Data Scientists de filtrer, agréger et regrouper par période
-- sans recalculer les attributs calendaires à chaque requête.

with date_spine as (

    -- Génère une ligne par jour couvert par les données disponibles
    -- La plage est extraite dynamiquement des relevés unifiés
    select
        generate_series(
            (select date_trunc('day', min(date_heure_utc)) from {{ ref('int_releves_unifies') }}),
            (select date_trunc('day', max(date_heure_utc)) from {{ ref('int_releves_unifies') }}),
            interval '1 day'
        )::date as date_jour

),

final as (

    select
        date_jour,
        extract(year  from date_jour)::smallint     as annee,
        extract(month from date_jour)::smallint     as mois,
        extract(day   from date_jour)::smallint     as jour,
        extract(dow   from date_jour)::smallint     as jour_semaine,   -- 0=dimanche
        extract(week  from date_jour)::smallint     as semaine_iso,
        extract(quarter from date_jour)::smallint   as trimestre,
        to_char(date_jour, 'TMMonth')               as nom_mois,
        to_char(date_jour, 'TMDay')                 as nom_jour,
        (extract(dow from date_jour) in (0, 6))     as est_weekend
    from date_spine

)

select * from final
