import tensorflow as tf

ROOT_HEIGHT = 4
import sys
from pathlib import Path
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[ROOT_HEIGHT]
sys.path.append(str(root))
try:
    sys.path.remove(str(parent))
except ValueError: # Already removed
    pass

from learning_to_learn.environment import Environment
from learning_to_learn.pupils.lstm_for_meta import Lstm, LstmFastBatchGenerator as BatchGenerator
from learning_to_learn.useful_functions import compose_hp_confs, get_num_exps_and_res_files
from learning_to_learn.launch_helpers import load_text_dataset

from learning_to_learn.optimizers.res_net_opt import ResNet4Lstm

import os

parameter_set_file_name = sys.argv[1]
save_path = os.path.join(parameter_set_file_name.split('.')[0], 'evaluation')
confs, _ = compose_hp_confs(parameter_set_file_name, save_path, chop_last_experiment=False)
confs.reverse()  # start with small configs
print("confs:", confs)

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)
dataset_path = os.path.join(*(['..']*ROOT_HEIGHT + ['datasets', 'text8.txt']))
valid_size = 500

add_metrics = ['bpc', 'perplexity', 'accuracy']
train_opt_add_feed = [
    {'placeholder': 'dropout', 'value': 1.},
    {'placeholder': 'optimizer_dropout_keep_prob', 'value': 1.}
]
opt_inf_add_feed = [
    {'placeholder': 'dropout', 'value': 1.},
    {'placeholder': 'optimizer_dropout_keep_prob', 'value': 1.}
]
valid_add_feed = [
    {'placeholder': 'dropout', 'value': 1.},
    {'placeholder': 'optimizer_dropout_keep_prob', 'value': 1.}
]

SHARE_TRAIN_DATA = True
checkpoints_path = os.path.join(*(['..']*ROOT_HEIGHT + ['lstm', 'start', 'checkpoints']))
the_only_pupil_restore_path = os.path.join(checkpoints_path, 'start')
PUPIL_NAME = 'COLD'
NUM_EXERCISES = 1
BATCH_SIZE = 32
NUM_UNROLLINGS = 10
train_size = BATCH_SIZE * NUM_UNROLLINGS
vocabulary, train_text, valid_text, _ = load_text_dataset('text8.txt', train_size, valid_size, None)
vocabulary_size = len(vocabulary)
NUM_OPTIMIZER_UNROLLINGS = 1
RESET_PERIOD = 1
OPTIMIZER_LEARNING_STEPS = 5000
RESULTS_COLLECT_INTERVAL = 1

env = Environment(
    pupil_class=Lstm,
    meta_optimizer_class=ResNet4Lstm,
    batch_generator_classes=BatchGenerator,
    vocabulary=vocabulary)

evaluation = dict(
    save_path=save_path,
    opt_inf_is_performed=True,
    opt_inf_stop=1,
    opt_inf_pupil_restore_paths={
        (PUPIL_NAME, the_only_pupil_restore_path)
    },
    opt_inf_additions_to_feed_dict=opt_inf_add_feed,
    opt_inf_validation_dataset_texts=[valid_text],
    opt_inf_train_dataset_texts=[train_text],
    opt_inf_results_collect_interval=1,
    validation_additions_to_feed_dict=valid_add_feed
)

kwargs_for_pupil_building = dict(
    batch_size=BATCH_SIZE,
    num_layers=1,
    num_nodes=[100],
    num_output_layers=1,
    num_output_nodes=[],
    vocabulary_size=vocabulary_size,
    embedding_size=150,
    num_unrollings=NUM_UNROLLINGS,
    init_parameter=3.,
    num_gpus=1,
    regime='training_with_meta_optimizer',
    additional_metrics=add_metrics,
    going_to_limit_memory=True
)

kwargs_for_optimizer_building = dict(
    regime='train',
    # regime='inference',
    num_optimizer_unrollings=NUM_OPTIMIZER_UNROLLINGS,
    num_exercises=NUM_EXERCISES,
    res_size=2000,
    permute=False,
    optimizer_for_opt_type='adam',
    additional_metrics=add_metrics
)

launch_kwargs = dict(
    allow_growth=True,
    save_path='training',
    result_types=['loss', 'bpc', 'perplexity', 'accuracy'],
    additions_to_feed_dict=train_opt_add_feed,
    pupil_restore_paths=[the_only_pupil_restore_path],
    # pupil_restore_paths=['debug_empty_meta_optimizer/not_learning_issue_es20_nn20/checkpoints/0'],
    reset_period=RESET_PERIOD,
    stop=OPTIMIZER_LEARNING_STEPS,
    train_dataset_texts=[train_text],
    opt_inf_is_performed=False,
    num_exercises=NUM_EXERCISES,
    vocabulary=vocabulary,
    batch_size=BATCH_SIZE,
    num_unrollings=NUM_UNROLLINGS,
    results_collect_interval=RESULTS_COLLECT_INTERVAL,
    batch_gen_init_is_random=False,
    # opt_inf_results_collect_interval=1,
    permute=False,
)

tf.set_random_seed(1)
for conf in confs:
    build_pupil_hyperparameters = dict(
    )
    build_optimizer_hyperparameters = dict(
        optimizer_init_parameter=conf['optimizer_init_parameter'],
        clip_norm=conf['clip_norm']
    )

    # other_hyperparameters={'dropout': [.3, .5, .7, .8, .9, .95]},
    other_hyperparameters = dict(
        learning_rate=dict(
            varying=dict(
                init=conf['learning_rate/init']
            ),
            fixed=dict(
                decay=.1,
                period=1e+4
            ),
            hp_type='built-in',
            type='exponential_decay'
        )
    )

    _, biggest_idx, _ = get_num_exps_and_res_files(save_path)
    if biggest_idx is None:
        initial_experiment_counter_value = 0
    else:
        initial_experiment_counter_value = biggest_idx + 1
    env.grid_search_for_meta(
        evaluation,
        kwargs_for_pupil_building,
        kwargs_for_optimizer_building,
        build_pupil_hyperparameters=build_pupil_hyperparameters,
        build_optimizer_hyperparameters=build_optimizer_hyperparameters,
        other_hyperparameters=other_hyperparameters,
        initial_experiment_counter_value=initial_experiment_counter_value,
        **launch_kwargs
    )
