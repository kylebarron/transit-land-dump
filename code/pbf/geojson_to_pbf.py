import sys

import click
import cligj

try:
    import schedule_tile_pb2
except ImportError:
    msg = 'Protobuf python code not generated'
    raise ImportError(msg)


@click.command()
@cligj.features_in_arg
def main(features):
    """Convert ScheduleStopPair GeoJSON LineStrings to PBF
    """
    # Instantiate objects
    # The `length` Deck.GL is expecting is the total number of coordinates, not
    # number of features
    positions = []
    timestamps = []
    indices = [0]
    index = 0
    n_coords = 0

    # Loop over features from stdin
    for feature in features:
        feature_type = feature['type']
        assert feature_type == 'Feature', 'top-level obj should be Feature'
        geom_type = feature['geometry']['type']
        assert geom_type == 'LineString', 'geometry must be LineString'

        coords = feature['geometry']['coordinates']
        for coord in coords:
            positions.extend(coord[:2])
            timestamps.append(coord[2])
            index += 1
            n_coords += 1

        indices.append(index)

    # Minimal validation
    msg = 'should be 2x positions for each timestamp'
    assert len(positions) == 2 * len(timestamps), msg
    msg = 'incorrect # of indices'
    assert indices[-1] == n_coords, msg

    # Create tile
    schedule_tile = schedule_tile_pb2.ScheduleTile()
    schedule_tile.positions.extend(positions)
    schedule_tile.timestamps.extend(timestamps)
    schedule_tile.startIndices.extend(indices)
    schedule_tile.length = n_coords

    # Write to stdout
    # https://stackoverflow.com/a/908440
    sys.stdout.buffer.write(schedule_tile.SerializeToString())


if __name__ == '__main__':
    main()
