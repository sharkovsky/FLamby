import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset

from flamby.utils import check_dataset_from_config


class HeartDiseaseRaw(Dataset):
    """Pytorch dataset containing all the features, labels and
    metadata for the Heart Disease dataset.

    Parameters
    ----------
    X_dtype : torch.dtype, optional
        Dtype for inputs `X`. Defaults to `torch.float32`.
    y_dtype : torch.dtype, optional
        Dtype for labels `y`. Defaults to `torch.int64`.
    debug : bool, optional,
        Whether or not to use only the part of the dataset downloaded in
        debug mode. Defaults to False.
    data_path: str
        If data_path is given it will ignore the config file and look for the
        dataset directly in data_path. Defaults to None.

    Attributes
    ----------
    data_dir: str
        Where data files are located
    labels : pd.DataFrame
        The labels as a dataframe.
    features: pd.DataFrame
        The features as a dataframe.
    centers: list[int]
        The list with the center ids associated with the dataframes.
    sets: list[str]
        For each sample if it is from the train or the test.
    X_dtype: torch.dtype
        The dtype of the X features output
    y_dtype: torch.dtype
        The dtype of the y label output
    debug: bool
        Whether or not we use the dataset with only part of the features
    """

    def __init__(
        self, X_dtype=torch.float32, y_dtype=torch.float32, debug=False, data_path=None
    ):
        """See description above"""
        if data_path is None:
            dict = check_dataset_from_config("fed_heart_disease", debug)
            self.data_dir = Path(dict["dataset_path"])
        else:
            if not (os.path.exists(data_path)):
                raise ValueError(f"The string {data_path} is not a valid path.")
            self.data_dir = Path(data_path)

        self.X_dtype = X_dtype
        self.y_dtype = y_dtype
        self.debug = debug

        self.centers_number = {
            "cleveland": 0,
            "hungarian": 1,
            "switzerland": 2,
            "va": 3,
        }

        self.features = pd.DataFrame()
        self.labels = pd.DataFrame()
        self.centers = []
        self.sets = []

        self.train_fraction = 0.66

        for center_data_file in self.data_dir.glob("*.data"):

            center_name = os.path.basename(center_data_file).split(".")[1]

            df = pd.read_csv(center_data_file, header=None)
            df = df.replace("?", np.NaN).drop([10, 11, 12], axis=1).dropna(axis=0)

            df = df.apply(pd.to_numeric)

            center_X = df.iloc[:, :-1]
            center_y = df.iloc[:, -1]

            self.features = pd.concat((self.features, center_X), ignore_index=True)
            self.labels = pd.concat((self.labels, center_y), ignore_index=True)

            self.centers += [self.centers_number[center_name]] * center_X.shape[0]

            # proposed modification to introduce shuffling before splitting the center
            nb = int(center_X.shape[0])
            current_labels = center_y.where(center_y == 0, 1, inplace=False)
            levels = np.unique(current_labels)
            if (len(np.unique(current_labels)) > 1) and all(
                [(current_labels == lev).sum() > 2 for lev in levels]
            ):
                stratify = current_labels
            else:
                stratify = None
            indices_train, indices_test = train_test_split(
                np.arange(nb),
                test_size=1.0 - self.train_fraction,
                train_size=self.train_fraction,
                random_state=43,
                shuffle=True,
                stratify=stratify,
            )

            for i in np.arange(nb):
                if i in indices_test:
                    self.sets.append("test")
                else:
                    self.sets.append("train")

        # encode dummy variables for categorical variables
        self.features = pd.get_dummies(self.features, columns=[2, 6], drop_first=True)
        self.features = [
            torch.from_numpy(self.features.loc[i].values.astype(np.float32)).to(
                self.X_dtype
            )
            for i in range(len(self.features))
        ]

        # keep 0 (no disease) and put 1 for all other values (disease)
        self.labels.where(self.labels == 0, 1, inplace=True)
        self.labels = torch.from_numpy(self.labels.values).to(self.X_dtype)

        # Normalization much needed
        self.features_tensor = torch.cat(
            [self.features[i][None, :] for i in range(len(self.features))], axis=0
        )
        self.mean_of_features = self.features_tensor.mean(axis=0)
        self.std_of_features = self.features_tensor.std(axis=0)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        assert idx < len(self.features), "Index out of range."

        X = (self.features[idx] - self.mean_of_features) / self.std_of_features
        y = self.labels[idx]

        return X, y


class FedHeartDisease(HeartDiseaseRaw):
    """
    Pytorch dataset containing for each center the features and associated labels
    for Heart Disease federated classification.
    One can instantiate this dataset with train or test data coming from either
    of the 4 centers it was created from or all data pooled.
    The train/test split are arbitrarily fixed.

    Parameters
    ----------
    center : int, optional
        Default to 0
    train : bool, optional
        Default to True
    pooled : bool, optional
        Whether to take all data from the 2 centers into one dataset, by
        default False
    X_dtype : torch.dtype, optional
        Dtype for inputs `X`. Defaults to `torch.float32`.
    y_dtype : torch.dtype, optional
        Dtype for labels `y`. Defaults to `torch.int64`.
    debug : bool, optional,
        Whether or not to use only the part of the dataset downloaded in
        debug mode. Defaults to False.
    data_path: str
        If data_path is given it will ignore the config file and look for the
        dataset directly in data_path. Defaults to None.
    """

    def __init__(
        self,
        center: int = 0,
        train: bool = True,
        pooled: bool = False,
        X_dtype: torch.dtype = torch.float32,
        y_dtype: torch.dtype = torch.float32,
        debug: bool = False,
        data_path: str = None,
    ):
        """Cf class description"""

        super().__init__(
            X_dtype=X_dtype, y_dtype=y_dtype, debug=debug, data_path=data_path
        )
        assert center in [0, 1, 2, 3]

        self.chosen_centers = [center]
        if pooled:
            self.chosen_centers = [0, 1, 2, 3]

        if train:
            self.chosen_sets = ["train"]
        else:
            self.chosen_sets = ["test"]

        to_select = [
            (self.sets[idx] in self.chosen_sets)
            and (self.centers[idx] in self.chosen_centers)
            for idx, _ in enumerate(self.features)
        ]

        self.features = [fp for idx, fp in enumerate(self.features) if to_select[idx]]
        self.sets = [fp for idx, fp in enumerate(self.sets) if to_select[idx]]
        self.labels = [fp for idx, fp in enumerate(self.labels) if to_select[idx]]
        self.centers = [fp for idx, fp in enumerate(self.centers) if to_select[idx]]
