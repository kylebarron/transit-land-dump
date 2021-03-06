-- Not currently used, currently all fields are text from the default csv import
CREATE TABLE ssp (
    origin_onestop_id TEXT,
    destination_onestop_id TEXT,
    route_onestop_id TEXT,
    route_stop_pattern_onestop_id TEXT,
    operator_onestop_id TEXT,
    feed_onestop_id TEXT,
    feed_version_sha1 TEXT,
    origin_timezone TEXT,
    destination_timezone TEXT,
    trip TEXT,
    trip_headsign TEXT,
    block_id TEXT,
    trip_short_name TEXT,
    wheelchair_accessible TEXT,
    bikes_allowed TEXT,
    pickup_type TEXT,
    drop_off_type TEXT,
    shape_dist_traveled REAL,
    origin_arrival_time TEXT,
    origin_departure_time TEXT,
    destination_arrival_time TEXT,
    destination_departure_time TEXT,
    origin_dist_traveled REAL,
    destination_dist_traveled REAL,
    service_start_date INT,
    service_end_date INT,
    window_start TEXT,
    window_end TEXT,
    origin_timepoint_source TEXT,
    destination_timepoint_source TEXT,
    frequency_start_time TEXT,
    frequency_end_time TEXT,
    frequency_headway_seconds TEXT,
    frequency_type TEXT,
    created_at TEXT,
    updated_at TEXT,
    service_days_of_week_0 INT,
    service_days_of_week_1 INT,
    service_days_of_week_2 INT,
    service_days_of_week_3 INT,
    service_days_of_week_4 INT,
    service_days_of_week_5 INT,
    service_days_of_week_6 INT,
)
