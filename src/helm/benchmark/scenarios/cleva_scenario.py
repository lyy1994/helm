import json
import os
import zipfile
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from helm.common.general import ensure_file_downloaded, ensure_directory_exists
from .scenario import Scenario, Instance, Reference, TRAIN_SPLIT, TEST_SPLIT, CORRECT_TAG, Input, Output


CLEVA_DATA_URL = "http://emnlp.clevaplat.com:8001/data"
CLEVA_DATA_PATH = "benchmark_output/scenarios/cleva"


@dataclass(frozen=True)
class PromptSetting:
    instructions: str
    input_noun: Optional[str] = None,
    newline_after_input_noun: bool = False,
    output_noun: Optional[str] = None,
    newline_after_output_noun: bool = False,


class CLEVAScenario(Scenario):
    """
    Scenario for CLEVA benchmark (https://arxiv.org/pdf/2308.04813.pdf).
    """

    def __init__(
        self,
        version: str,
        task: str,
        subtask: str,
    ):
        """
        Initializes CLEVA scenario.
        Args:
            version: String identifier for version in a format of 'v[1-9]*([0-9])'.
            task: String identifier for task.
            subtask: String identifier for subtask.
        """
        super().__init__()
        self.task = task
        self.subtask = subtask
        self.version = version
        self.splits: Dict[str, str] = {
            "train": TRAIN_SPLIT,
            "test": TEST_SPLIT,
        }

    @classmethod
    def download_dataset(cls, version: str):
        download_url: str = CLEVA_DATA_URL + f"/{version}/data.zip"
        data_dir: str = os.path.join(CLEVA_DATA_PATH, "data", version)
        ensure_directory_exists(data_dir)
        ensure_file_downloaded(source_url=download_url, target_path=os.path.join(data_dir, "data.zip"))

        with zipfile.ZipFile(os.path.join(data_dir, "data.zip"), 'r') as zip_ref:
            zip_ref.extractall(data_dir)

    def load_dataset(self) -> Dict[str, List[Dict[str, Any]]]:
        data_dir: str = os.path.join(CLEVA_DATA_PATH, "data", self.version, self.task)
        if self.subtask:
            data_dir: str = os.path.join(data_dir, self.subtask)

        dataset: Dict[str, List[Dict[str, Any]]] = {}
        for split in self.splits.keys():

            with open(os.path.join(data_dir, f"{split}.jsonl"), "r") as fin:
                dataset[split] = []
                for line in fin.readlines():
                    dataset[split].append(json.loads(line))

        return dataset

    def get_instances(self) -> List[Instance]:
        # Download the raw data
        dataset = self.load_dataset()

        # Read all the instances
        instances: List[Instance] = []
        for split in self.splits:
            for row in dataset[split]:
                instances.append(self.process_instance(row, self.splits[split]))

        return instances

    def process_instance(self, row: Dict[str, Any], split: str) -> Instance:
        text: str = row["text"]
        if "choices" in row.keys():
            answers: List[str] = row["choices"]
            correct_choice: List[int] = row["label"]
            
            correct_answer: List[str] = [answers[idx] for idx in correct_choice]

            def answer_to_reference(answer: str) -> Reference:
                return Reference(Output(text=answer), tags=[CORRECT_TAG] if answer in correct_answer else [])
            
            references: list[Instance] = list(map(answer_to_reference, answers))
        else:
            answers: List[str] = row["label"]
            references: list[Instance] = [Reference(Output(text=answer), tags=[CORRECT_TAG]) for answer in answers]

        instance = Instance(
            input=Input(text=text),
            references=references,
            split=split,
        )
        return instance
    
    @classmethod
    def get_prompt_setting(cls, task: str, subtask: str, version: str) -> PromptSetting:
        # TODO: get prompt setting online
        if task == "text_classification":
            prompt_setting = PromptSetting(
                instructions="以下文本属于哪个类别？",
                input_noun="问题",
                output_noun="答案",
            )
        elif task == "opinion_mining":
            prompt_setting = PromptSetting(
                instructions="请根据以下陈述，挖掘出陈述中的观点目标。",
                input_noun="陈述",
                newline_after_input_noun=False,
                output_noun="主体",
                newline_after_output_noun=False,
            )
        else:
            raise ValueError(f"The specified task '{task}' is not supported")
        return prompt_setting


class CLEVATextClassificationScenario(CLEVAScenario):
    """
    The text classifiation task of CLEVA benchmark.

    An example is:
        以下文本属于哪个类别？

        问题: 自考本科选择什么专业好？
        A. 体育
        B. 财经
        C. 娱乐
        D. 军事
        E. 文化
        F. 旅游
        G. 游戏
        H. 农业
        I. 股票
        J. 教育
        K. 国际
        L. 科技
        M. 汽车
        N. 房屋
        O. 故事
        答案: J

        问题: 劲爆！新能源电池全新变化，固态电池有望成风口，受益龙头蓄势待
        A. 体育
        B. 财经
        C. 娱乐
        D. 军事
        E. 文化
        F. 旅游
        G. 游戏
        H. 农业
        I. 股票
        J. 教育
        K. 国际
        L. 科技
        M. 汽车
        N. 房屋
        O. 故事
        答案:

    Target: M
    """

    name = "cleva_text_classification"
    description = "Text classification task in CLEVA benchmark"
    tags = ["multiple_choice"]


class CLEVAOpinionMiningScenario(CLEVAScenario):
    """
    The opinion mining task of CLEVA benchmark.

    An example is:
        请根据以下陈述，挖掘出陈述中的观点目标。

        陈述: 从亚龙湾出发，大概40分钟左右的车程即可到达码头，转乘轮渡抵达蜈支洲岛。
        主体: 蜈支洲岛
        
        陈述: 这是一座被称为最美大学的校园，座山面海是厦门大学得天独厚的自然条件。
        主体:

    Target: 厦门大学
    """

    name = "cleva_opinion_mining"
    description = "Opinion mining task in CLEVA benchmark"
    tags = ["opinion_mining"]
