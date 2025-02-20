import os
import re

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# import numpy as np
import pandas as pd
import seaborn as sns

sns.set()


# utils to fetch number of clients from each dataset names
def get_nb_clients_from_dataset(name_arg):
    print(name_arg)
    return getattr(
        __import__(f"flamby.datasets.{name_arg}", fromlist=["NUM_CLIENTS"]),
        "NUM_CLIENTS",
    )


strategies_names = [
    "FedAvg",
    "Scaffold",
    "FedProx",
    "Cyclic",
    "FedAdagrad",
    "FedYogi",
    "FedAdam",
]
# Filtering only 100 updates strategies
strategies = [strat + str(100) for strat in strategies_names]

dir_path = os.path.dirname(os.path.realpath(__file__))

# TODO remove only there for debugging purposes
# for name in ["fed_lidc_idri", "fed_ixi", "fed_camelyon16"]:
#     current_num_clients = get_nb_clients_from_dataset(name)
#     methods = strategies + ['Pooled Training'] +  ["Local " + str(i) for i in range(current_num_clients)]
#     # duplicate methods
#     methods = [m for m in methods for _ in range(current_num_clients)]
#     nrows = len(methods)
#     metrics = np.random.uniform(0, 1, nrows)
#     tests = [""] * nrows
#     df = pd.DataFrame({"Method": methods, "Metric": metrics, "Test": tests})
#     df.to_csv(os.path.join(dir_path, f"results_benchmark_{name}.csv"), index=False)

dataset_names = []
results = []
# directory names should be as below
dirs_multiple_seeds = [
    os.path.join(dir_path, "results_benchmark_fed_camelyon16"),
    os.path.join(dir_path, "results_benchmark_fed_lidc_idri"),
    os.path.join(dir_path, "results_benchmark_fed_ixi"),
    os.path.join(dir_path, "results_benchmark_fed_tcga_brca"),
    os.path.join(dir_path, "results_benchmark_fed_kits19"),
    os.path.join(dir_path, "results_benchmark_fed_isic2019"),
    os.path.join(dir_path, "results_benchmark_fed_heart_disease"),
]
for dir in dirs_multiple_seeds:
    csv_files = [os.path.join(dir, f) for f in os.listdir(dir)]
    result_pds = [pd.read_csv(f) for f in csv_files]
    df = pd.concat(result_pds, ignore_index=True)
    results.append(df)
    dataset_names.append("_".join(dir.split("/")[-1].split(".")[0].split("_")[2:]))

fig, axs = plt.subplots(3, 3, sharey=True, figsize=(30, 22), dpi=80)
# Keep Room for Strategy labels
fig.subplots_adjust(hspace=5.0)
flattened_axs = axs.flatten()

palette = sns.color_palette("mako", 14)
for idx, (ax, res, name) in enumerate(zip(flattened_axs, results, dataset_names)):
    if name == dataset_names[-1]:
        ax = flattened_axs[7]
    # Remove pooled results
    res = res.loc[res["Test"] != "Pooled Test"]
    # if "lidc" in name.lower():
    #     res = res[["Method", "Metric"]]
    # else:
    #     res = res[["Method", "Metric", "seed"]]

    current_num_clients = get_nb_clients_from_dataset(name)
    current_methods = (
        ["Pooled Training"]
        + ["Local " + str(i) for i in range(current_num_clients)]
        + strategies
    )

    res = res.loc[res["Method"].isin(current_methods)]

    assert len(res["Method"].unique()) == len(current_methods)

    if not ("lidc" in name.lower()):
        assert len(res["seed"].unique()) == 5
        for m in current_methods:
            assert len(res.loc[res["Method"] == m].index) == (current_num_clients * 5)
    else:
        for m in current_methods:
            assert len(res.loc[res["Method"] == m].index) == (current_num_clients)

    # Pretiifying render
    res = res.rename(columns={"Method": "Training Method"})
    res.loc[res["Training Method"] == "Pooled Training", "Training Method"] = "Pooled"
    current_methods_display = [re.sub(" Training", "", c) for c in current_methods]

    # Messing with palettes to keep the same color for pooled and strategies
    current_palette = [palette[0]] + palette[1 : (current_num_clients + 1)] + palette[7:]
    assert len(current_palette) == len(current_methods_display)
    # print(current_palette[len(current_methods_display) -1])
    sns.barplot(
        ax=ax,
        x="Training Method",
        y="Metric",
        data=res,
        order=current_methods_display,
        capsize=0.05,
        saturation=2,
        errcolor="gray",
        errwidth=2,
        palette=current_palette,
    )
    # We remove the number of updates which will go into the legend
    labels = [re.sub("100", "", item.get_text()) for item in ax.get_xticklabels()]

    # TODO cannot make fontsize change effective on those labels for some reasons

    ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
    ticks_loc = ax.get_yticks().tolist()

    ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    label_format = "{:.1f}"
    ax.set_yticklabels([label_format.format(y) for y in ticks_loc], fontsize=35)

    ax.set_xticklabels(labels, rotation=90, fontsize=35, fontweight="heavy")
    ax.set_xlabel(ax.get_xlabel(), fontsize=35, fontweight="heavy")
    ax.set_ylabel(ax.get_ylabel(), fontsize=35, fontweight="heavy")

    # We only display the xlabel on figures from the second row except the 4th one because it has no counterpart(label can be removed entirely)
    # and y label on the first figure of each row
    if idx < 3 or idx == 4:
        ax.set(xlabel=None)
    if idx not in [0, 3, 7]:
        ax.set(ylabel=None)

    # ugly but no time
    # current_title = " ".join([word.capitalize() for word in name.split("_")])
    title_dicts = {
        "fed_camelyon16": "Fed-Camelyon16",
        "fed_lidc_idri": "Fed-LIDC-IDRI",
        "fed_ixi": "Fed-IXI",
        "fed_tcga_brca": "Fed-TCGA-BRCA",
        "fed_kits19": "Fed-KITS2019",
        "fed_isic2019": "Fed-ISIC2019",
        "fed_heart_disease": "Fed-Heart-Disease",
    }
    current_title = title_dicts[name]
    ax.set_title(current_title, fontsize=45, fontweight="heavy")

# Hide the last plot
flattened_axs[-3].set_visible(False)
flattened_axs[-1].set_visible(False)
plt.tight_layout()
plt.savefig("plot_results_benchmarks.png")
plt.savefig("plot_results_benchmarks.eps")
