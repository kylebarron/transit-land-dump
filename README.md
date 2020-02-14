# All transit

[![Build Status](https://travis-ci.org/kylebarron/all-transit.svg?branch=master)](https://travis-ci.org/kylebarron/all-transit)

[![Example Screenshot](assets/overview_screenshot.png)](https://kylebarron.dev/all-transit)

[Website: https://kylebarron.dev/all-transit](https://kylebarron.dev/all-transit)

All transit in the continental US, as reported by the [Transitland
database](https://transit.land). Inspired by [_All
Streets_](https://benfry.com/allstreets/map5.html).

## Website

The code for the website is in `site/`. It uses React, Gatsby, Deck.gl, and
React Map GL/Mapbox GL JS.

## Data

Most of the data-generating code for this project is done in Bash,
[`jq`](https://stedolan.github.io/jq/), GNU Parallel, SQLite, and a couple
Python scripts. Data is kept in _newline-delimited JSON_ and _newline-delimited
GeoJSON_ for all intermediate steps to facilitate streaming and keep memory use
low.

### Data Download

Clone this Git repository and install the Python package I wrote to easily
access the Transitland API.
```bash
git clone https://github.com/kylebarron/all-transit
cd all-transit
pip install transitland-wrapper
mkdir -p data
```

Each of the API endpoints allows for a bounding box. At first, I tried to just
pass a bounding box of the entire United States to these APIs and page through
the results. Unsurprisingly, that method isn't successful for the endpoints that
have more data to return, like stops and schedules. I found that for the
schedules endpoint, the API was really slow and occasionally timed out when I
was trying to request something with `offset=100000`, because presumably it
takes a lot of time to find the 100,000th row of a given query.

Because of this, I found it best in general to split API queries into smaller
pieces, by using e.g. operator ids or route ids.

#### Operators

Download all operators whose service area intersects the continental US, and
then extract their identifiers.
```bash
# All operators
transitland operators \
    --geometry data/gis/states/states.shp \
    > data/operators.geojson

# All operator `onestop_id`s
cat data/operators.geojson \
    | jq '.properties.onestop_id' \
    | uniq \
    | \
    tr -d \" \
    > data/operator_onestop_ids.txt
```

#### Routes

I downloaded routes by the geometry of the US, and then later found it best to
split the response into separate files by operator. If I were to run this
download again, I'd just download routes by operator to begin with.

```bash
# All routes
transitland routes \
    --geometry data/gis/states/states.shp \
    > data/routes.geojson

# Split these routes into different files by operator
mkdir -p data/routes/
cat data/operator_onestop_ids.txt | while read operator_id
do
    cat data/routes.geojson \
        | jq -c "if .properties.operated_by_onestop_id == \"$operator_id\" then . else empty end" \
        > data/routes/$operator_id.geojson
done
```

Now that the routes are downloaded, I extract the identifiers for all
`RouteStopPattern`s and `Route`s.
```bash
# All route stop patterns `onestop_id`s for those routes:
cat data/routes.geojson \
    | jq '.properties.route_stop_patterns_by_onestop_id[]' \
    | uniq \
    | tr -d \" \
    > data/route_stop_patterns_by_onestop_id.txt

# All route onestop_ids
cat data/routes.geojson \
    | jq '.properties.onestop_id' \
    | uniq \
    | tr -d \" \
    > data/routes_onestop_ids.txt
```

In order to split up how I later call the `ScheduleStopPairs` API endpoint, I
split the `Route` identifiers into sections. There are just shy of 15,000 route
identifiers, so I split into 5 files of roughly equal 3,000 route identifiers.
```bash
# Split into fifths so that I can call the ScheduleStopPairs API in sections
cat routes_onestop_ids.txt \
    | sed -n '1,2999p;3000q' \
    > routes_onestop_ids_1.txt
cat routes_onestop_ids.txt \
    | sed -n '3000,5999p;6000q' \
    > routes_onestop_ids_2.txt
cat routes_onestop_ids.txt \
    | sed -n '6000,8999p;9000q' \
    > routes_onestop_ids_3.txt
cat routes_onestop_ids.txt \
    | sed -n '9000,11999p;12000q' \
    > routes_onestop_ids_4.txt
cat routes_onestop_ids.txt \
    | sed -n '12000,15000p;15000q' \
    > routes_onestop_ids_5.txt
```

#### Stops

`Stops` are points along a `Route` or `RouteStopPattern` where passengers may
get on or off.

Downloading stops by operator was necessary to keep the server from paging
through too long of results. I was stupid and concatenated them all into a
single file, which I later saw that I needed to split with `jq`. If I were
downloading these again, I'd write each `Stops` response into a file named by
operator.
```bash
# All stops
rm data/stops.geojson
cat data/operator_onestop_ids.txt | while read operator_id
do
    transitland stops \
        --served-by $operator_id \
        --per-page 1000 \
        >> data/stops.geojson
done

# Split these stops into different files by operator
# NOTE: Again, if I were doing this again, I'd just write into individual files
# in the above step, but I didn't want to spend more time calling the API
# server.
mkdir -p data/stops/
cat data/operator_onestop_ids.txt | while read operator_id
do
    cat data/stops.geojson \
        | jq -c "if .properties.operators_serving_stop | any(.operator_onestop_id == \"$operator_id\") then . else empty end" \
        > data/stops/$operator_id.geojson
done
```

#### Route Stop Patterns

`RouteStopPattern`s are portions of a route. I think an easy way to think of the
difference is the a `Route` can be a MultiLineString, while a `RouteStopPattern`
is always a LineString.

So far I haven't actually needed to use `RouteStopPattern`s for anything. I
would've ideally matched `ScheduleStopPair`s to `RouteStopPattern`s instead of
to `Route`s, but I found that some `ScheduleStopPair` have missing
`RouteStopPattern`s, while `Route` is apparently never missing.

```bash
# All route-stop-patterns (completed relatively quickly, overnight)
transitland onestop-id \
    --file data/route_stop_patterns_by_onestop_id.txt \
    > data/route-stop-patterns.json
```

#### Schedule Stop Pairs

`ScheduleStopPair`s are edges along a `Route` or `RouteStopPattern` that define
a single instance of transit moving between a pair of stops along the route.

I at first tried to download this by `operator_id`, but even that stalled the
server because some operators in big cities have millions of different
`ScheduleStopPair`s. Instead I downloaded by `route_id`.

Apparently you can only download by `Route` and not by `RouteStopPattern`, or
else I probably would've chosen the latter, which might've made associating
`ScheduleStopPair`s to geometries easier.

I used each fifth of the `Route` identifiers from earlier so that I could make
sure each portion was correctly downloaded.
```bash
# All schedule-stop-pairs
# Best to loop over route_id, not operator_id
rm data/ssp.json
mkdir -p data/ssp/
for i in {1..5}; do
    cat data/routes_onestop_ids_${i}.txt | while read route_id
    do
        transitland schedule-stop-pairs \
        --route-onestop-id $route_id \
        --per-page 1000 --active \
        | gzip >> data/ssp/ssp${i}.json.gz
    done
done
```

### Vector tiles for Operators, Routes, Stops

I generate vector tiles for the routes, operators, and stops. I have `jq`
filters in `code/jq/` to reshape the GeoJSON into the format I want, so that the
correct properties are included in the vector tiles.

In order to keep the size of the vector tiles small:

- The `stops` layer is only included at zoom 11
- The `routes` layer only includes metadata about the identifiers of the stops
  that it passes at zoom 11

```bash
# Writes mbtiles to data/routes.mbtiles
# The -c is important so that each feature gets output onto a single line
cat data/routes.geojson \
    | jq -c -f code/jq/routes.jq \
    | bash code/tippecanoe/routes.sh

# Writes mbtiles to data/operators.mbtiles
bash code/tippecanoe/operators.sh data/operators.geojson

# Writes mbtiles to data/stops.mbtiles
# The -c is important so that each feature gets output onto a single line
cat data/stops.geojson \
    | jq -c -f code/jq/stops.jq \
    | bash code/tippecanoe/stops.sh
```

Combine into single mbtiles
```bash
tile-join \
    -o data/all.mbtiles \
    --no-tile-size-limit \
    --force \
    stops.mbtiles operators.mbtiles routes.mbtiles
```

Then publish! Host on a small server with
[`mbtileserver`](https://github.com/consbio/mbtileserver) or export the
`mbtiles` to a directory of individual tiles with
[`mb-util`](https://github.com/mapbox/mbutil) and upload the individual files to
S3.

### Schedules

The schedule component is my favorite part of the project. You can see dots
moving around that correspond to transit vehicles: trains, buses, ferries. This
data is _not simulated_, it takes actual schedule information from the
Transitland API and matches it to route geometries.

I use the deck.gl
[`TripsLayer`](https://deck.gl/#/documentation/deckgl-api-reference/layers/trips-layer)
to render the schedule data as an animation. That means that I need to figure
out the best way to transport three-dimensional `LineStrings` (where the third
dimension refers to time) to the client. Unfortunately, at this time Tippecanoe
[doesn't support three-dimensional
coordinates](https://github.com/mapbox/tippecanoe/issues/714). The
recommendation in that thread was to reformat to have individual points with
properties. That would make it harder to associate the points to lines, however.
I eventually decided it was best to pack the data into tiled
gzipped-minified-GeoJSON. And since I know that all features are `LineStrings`,
and since I have no properties that I care about, I take only the coordinates,
so that the data the client receives is like:

```json
[
    [
        [
            0, 1, 2
        ],
        [
            1, 2, 3
        ]
    ],
    [
        []
        ...
    ]
]
```

I currently store the third coordinate as seconds of the day. So that 4pm is `16
* 60 * 60 = 57000`.

In order to make the data download manageable, I cut each GeoJSON into xyz map
tiles, so that only data pertaining to the current viewport is loaded. For dense
cities like Washington DC and New York City, some of the LineStrings are very
dense, so I cut the schedule tiles into full resolution at zoom 13, and then
generate overview tiles for lower zooms that contain a fraction of the features
of their child tiles.

I generated tiles in this manner down to zoom 2, but discovered that performance
was very poor on lower-powered devices like my phone. Because of that, I think
it's best to have the schedule feature disabled by default.

#### Data Processing

I originally tried to do everything with `jq`, but the schedule data for all
routes in the US as uncompressed JSON is >100GB and things were too slow. I
tried SQLite and it's pretty amazing.

To import `ScheduleStopPair` data into SQLite, I first converted the JSON files
to CSV:
```bash
# Create CSV file with data
mkdir -p data/ssp_sqlite/
for i in {1..5}; do
    # header line
    gunzip -c data/ssp/ssp${i}.json.gz \
        | head -n 1 \
        | jq -rf code/ssp/ssp_keys.jq \
        | gzip \
        > data/ssp_sqlite/ssp${i}.csv.gz
    # Data
    gunzip -c data/ssp/ssp${i}.json.gz \
        | jq -rf code/ssp/ssp_values.jq \
        | gzip \
        >> data/ssp_sqlite/ssp${i}.csv.gz
done
```

Then import the CSV files into SQLite:
```bash
for i in {1..5}; do
    gunzip -c data/ssp_sqlite/ssp${i}.csv.gz \
        | sqlite3 -csv data/ssp_sqlite/ssp.db '.import /dev/stdin ssp'
done
```

Create SQLite index on `route_id`
```bash
sqlite3 data/ssp_sqlite/ssp.db \
    'CREATE INDEX route_onestop_id_idx ON ssp(route_onestop_id);'
```

I found it best to loop over `route_id`s when matching schedules to route
geometries. Here I create a crosswalk with the operator id for each route, so
that I can pass to my Python script 1) `ScheduleStopPair`s pertaining to a
route, 2) `Stops` by operator and 3) `Routes` by operator.
```bash
# Make xw with route_id: operator_id
cat data/routes.geojson \
    | jq -c '{route_id: .properties.onestop_id, operator_id: .properties.operated_by_onestop_id}' \
    > data/route_operator_xw.json
```

Here's the meat of connecting schedules to route geometries. The bash script calls `code/schedules/ssp_geom.py`, and the general process of that script is:

1. Load stops and routes for the operator in dictionaries
2. Load provided `ScheduleStopPair`s from stdin
3. Iterate over every `ScheduleStopPair`, call this `ssp`:
    1. Find the starting and ending stops of the `ssp`, and record their `Point` geometries.
    2. Find the route the `ssp` corresponds to and record its geometry.
    3. For the starting and ending stops, find the closest point on the route.
        Sometimes the route will actually be a `MultiLineString`, in which case
        I try to keep the `LineString` that's closest to both the starting and
        ending stops.
    4. Now that I have a single `LineString`, split it by the starting and
        ending stops, so that I have only the part of the route between those
        two stops.
    5. Get the time at which the vehicle leaves the start stop and at which it
        arrives at the destination stop. Then linearly interpolate this along
        every coordinate of the `LineString`. This way, the finalized
        `LineString`s have the same geometry as the original routes, and every
        coordinate has a time.

```bash
# Loop over _routes_
num_cpu=15
for i in {1..5}; do
    cat data/routes_onestop_ids_${i}.txt \
        | parallel -P $num_cpu bash code/schedules/ssp_geom.sh {}
done
```

Now in `data/ssp_geom` I have a newline-delimited GeoJSON file for every route.
I take all these individual features and cut them into individual tiles for a
zoom that has all the original data with no simplification, which I currently
have as zoom 13.
```bash
rm -rf data/ssp_geom_tiles
mkdir -p data/ssp_geom_tiles
find data/ssp_geom/ -type f -name 'r-*.geojson' -exec cat {} \; \
    | uniq \
    | python code/tile/tile_geojson.py \
            `# Set minimum and maximum tile zooms` \
            -z 13 -Z 13 \
            `# Only keep LineStrings` \
            --allowed-geom-type 'LineString' \
            `# Write tiles into the following root dir` \
            -d data/ssp_geom_tiles
```

Create overview tiles for lower zooms
```bash
python code/tile/create_overview_tiles.py \
    --min-zoom 2 \
    --existing-zoom 13 \
    --tile-dir data/ssp_geom_tiles \
    --max-coords 150000
```

Then compress these tiles
```bash
rm -rf data/ssp_geom_tiles_comp
mkdir -p data/ssp_geom_tiles_comp
for file in data/ssp_geom_tiles/**/*.geojson; do
    z="$(echo $file | awk -F'/' '{print $(NF-2)}')"
    x="$(echo $file | awk -F'/' '{print $(NF-1)}')"
    y="$(basename $file .geojson)"
    mkdir -p data/ssp_geom_tiles_comp/$z/$x
    # Take only the coordinates, minified, and gzip them
    cat $file \
    `# Take only the coordinates of each GeoJSON record` \
    | jq -c '.geometry.coordinates' \
    `# Convert JSONlines to JSON` \
    | jq -cs '.' \
    | gzip > data/ssp_geom_tiles_comp/$z/$x/$y.json
done
```

Upload to AWS
```bash
aws s3 cp \
    data/ssp_geom_tiles_comp s3://data.kylebarron.dev/all-transit/schedule/4_16-20/ \
    --recursive \
    --content-type application/json \
    --content-encoding gzip \
    `# Set to public read access` \
    --acl public-read
```
