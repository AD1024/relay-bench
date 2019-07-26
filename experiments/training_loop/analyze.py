import argparse

import numpy as np

from validate_config import validate
from common import write_status, write_json, render_exception
from analysis_util import trials_average_time, mean_of_means

def main(data_dir, config_dir, output_dir):
    config, msg = validate(config_dir)
    if config is None:
        write_status(output_dir, False, msg)
        return

    frameworks = config['frameworks']
    devices = config['devices']
    num_reps = config['n_inputs']
    num_classes = list(config['num_classes'])[0]
    batch_size = list(config['batch_sizes'])[0]
    epochs = config['epochs']

    listing_settings = {
        'Relay': 'relay',
        'Keras': 'keras'
    }

    fieldnames = ['device', 'batch_size', 'num_classes', 'epochs']

    # output averages on each network for each framework and each device
    ret = {}
    for dev in devices:
        ret[dev] = {}
        for listing, framework in listing_settings.items():
            ret[dev][listing] = {}
            for epoch_count in epochs:
                field_values = {
                    'device': dev,
                    'batch_size': batch_size,
                    'num_classes': num_classes,
                    'epochs': epoch_count
                }

                mean, success, msg = trials_average_time(data_dir, framework, 'training_loop', num_reps,
                                                         fieldnames, field_values)
                if not success:
                    write_status(output_dir, False, msg)
                    return
                ret[dev][listing][epoch_count] = mean

    write_json(output_dir, 'data.json', ret)
    write_status(output_dir, True, 'success')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True)
    parser.add_argument("--config-dir", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    args = parser.parse_args()
    main(args.data_dir, args.config_dir, args.output_dir)
