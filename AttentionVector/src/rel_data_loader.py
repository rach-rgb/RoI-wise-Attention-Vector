import itertools
import numpy as np
import torch

from detectron2.data.catalog import DatasetCatalog, MetadataCatalog
from detectron2.data.detection_utils import check_metadata_consistency
from detectron2.data import (
    load_proposals_into_dataset,
)


# modified get_detection_dataset_dicts
def light_detection_datasets_dict(dataset_names, filter_empty=True, min_keypoints=0, proposal_files=None):
    assert len(dataset_names)
    dataset_dicts = [DatasetCatalog.get(dataset_name) for dataset_name in dataset_names]
    for dataset_name, dicts in zip(dataset_names, dataset_dicts):
        assert len(dicts), "Dataset '{}' is empty!".format(dataset_name)

    if proposal_files is not None:
        assert len(dataset_names) == len(proposal_files)
        # load precomputed proposals from proposal files
        dataset_dicts = [
            load_proposals_into_dataset(dataset_i_dicts, proposal_file)
            for dataset_i_dicts, proposal_file in zip(dataset_dicts, proposal_files)
        ]

    dataset_dicts = list(itertools.chain.from_iterable(dataset_dicts))

    has_instances = "annotations" in dataset_dicts[0]

    if has_instances:
        try:
            check_metadata_consistency("thing_classes", dataset_names)
        except AttributeError:  # class names are not available for this dataset
            pass
    return dataset_dicts


def get_rel_classes(cfg):
    dataset_dicts = light_detection_datasets_dict(
        cfg.DATASETS.TRAIN,
        filter_empty=cfg.DATALOADER.FILTER_EMPTY_ANNOTATIONS,
        min_keypoints=cfg.MODEL.ROI_KEYPOINT_HEAD.MIN_KEYPOINTS_PER_IMAGE
        if cfg.MODEL.KEYPOINT_ON
        else 0,
        proposal_files=cfg.DATASETS.PROPOSAL_FILES_TRAIN if cfg.MODEL.LOAD_PROPOSALS else None,
    )
    class_names = MetadataCatalog.get(cfg.DATASETS.TRAIN[0]).thing_classes

    num_classes = len(class_names)
    appearance = torch.zeros(num_classes, dtype=torch.float32, device='cuda:0')
    pair_appearance = torch.zeros([num_classes+1, num_classes+1], dtype=torch.float32, device='cuda:0')

    for entry in dataset_dicts:
        annos = entry["annotations"]
        classes = [x["category_id"] for x in annos if not x.get("iscrowd", 0)]
        classes = set(classes)
        for c1 in classes:
            for c2 in classes:
                if c1 == c2:
                    continue
                pair_appearance[c1][c2] = pair_appearance[c1][c2] + 1
            appearance[c1] = appearance[c1] + 1

    for c in range(0, num_classes):
        if appearance[c] != 0:
            pair_appearance[c] = pair_appearance[c] / appearance[c]

    del appearance

    return pair_appearance