import sys

from matplotlib import pyplot as plt
from skorch.callbacks import LRScheduler

sys.path.append('..')

import numpy as np
import torch

from sklearn.metrics import accuracy_score
from skorch.dataset import Dataset
from skorch.helper import predefined_split

from module.crowd_layer_skorch import CrowdLayerSkorch
from module.ground_truth_module import ClassifierModule
from data_set.dataset import load_dataset

import mlflow

def seed_everything(seed=42):
    np.random.seed(seed)
    torch.manual_seed(seed)


if __name__ == '__main__':
    seed = 42
    MISSING_LABEL = -1

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    seed_everything(seed)
    X_train, y_train, y_train_true, X_valid, y_valid_true, X_test, y_test_true = load_dataset()

    dataset_classes = np.unique(y_test_true)
    n_classes = len(dataset_classes)
    n_features = X_train.shape[1]

    valid_ds = Dataset(X_valid, y_valid_true)

    mlflow.set_tracking_uri(uri='/Users/chengjiaying/BachelorProjekt/Crowd_Layer/tracking')
    exp = mlflow.get_experiment_by_name(name='Crowd-Layer-05-19')
    experiment_id = mlflow.create_experiment(name='Crowd-Layer-05-19') if exp is None else exp.experiment_id

    with mlflow.start_run(experiment_id=experiment_id):
        hyper_dict = {
            'max_epochs': 250,
            'batch_size': 64,
            'lr': 0.01,
            'optimizer__weight_decay': 0.0001
        }
        lr_scheduler = LRScheduler(policy="CosineAnnealingLR", T_max=hyper_dict['max_epochs'])

        gt_net = ClassifierModule(n_classes=n_classes, dropout=0.0)
        net = CrowdLayerSkorch(
            module__n_annotators=44,
            module__gt_net=gt_net,
            classes=dataset_classes,
            missing_label=MISSING_LABEL,
            cost_matrix=None,
            random_state=1,
            train_split=predefined_split(valid_ds),
            verbose=False,
            optimizer=torch.optim.AdamW,
            device=device,
            callbacks=[lr_scheduler],
            **hyper_dict,
        )

        net.initialize()
        print(net.lr)

        mlflow.log_params(hyper_dict)

        net.fit(X_train, y_train)

        y_train_pred = net.predict(X_train)
        train_accuracy = accuracy_score(y_train_true, y_train_pred) #

        y_pred = net.predict(X_test)
        test_accuracy = accuracy_score(y_pred, y_test_true)
        metrics = {
            'train_accuracy': train_accuracy,
            'test_accuracy': test_accuracy,
        }

        mlflow.log_metrics(metrics)
        print(metrics)

        print(net.module_.annotator_layers[0].weight)

        proba_annotator_pref = net.predict_annotator_perf(X_test[0:1], False)
        print(proba_annotator_pref)

        history = net.history
        train_loss = history[:, 'train_loss']
        plt.plot(train_loss)
        plt.title(f'train: {metrics["train_accuracy"]}; test: {metrics["test_accuracy"]}')
        plt.show()