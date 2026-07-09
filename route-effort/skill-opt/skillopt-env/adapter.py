"""route-effort environment adapter for SkillOpt."""
from __future__ import annotations

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter
from skillopt.envs.route_effort.dataloader import RouteEffortDataLoader
from skillopt.envs.route_effort.rollout import run_batch


class RouteEffortAdapter(EnvAdapter):
    """route-effort environment adapter."""

    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        split_mode: str = "ratio",
        split_ratio: str = "8:1:1",
        split_seed: int = 42,
        split_output_dir: str = "",
        exec_timeout: int = 120,
        workers: int = 8,
        analyst_workers: int = 8,
        failure_only: bool = False,
        minibatch_size: int = 5,
        edit_budget: int = 4,
        seed: int = 42,
        limit: int = 0,
        max_completion_tokens: int = 4096,
        **kwargs,
    ):
        self.exec_timeout = exec_timeout
        self.workers = workers
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.max_completion_tokens = max_completion_tokens

        self.loader = RouteEffortDataLoader(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.loader.setup(cfg)

    def get_dataloader(self):
        return self.loader

    def build_train_env(self, batch_size: int, seed: int, **kwargs) -> list[dict]:
        """Build train environment."""
        batch = self.loader.build_train_batch(batch_size=batch_size, seed=seed, **kwargs)
        return list(batch.payload or [])

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs) -> list[dict]:
        """Build evaluation environment."""
        batch = self.loader.build_eval_batch(env_num=env_num, split=split, seed=seed, **kwargs)
        return list(batch.payload or [])

    def build_val_env(self, batch_spec: BatchSpec) -> list[dict]:
        """Build validation environment (deprecated, use build_eval_env)."""
        return self.loader.load_split("val", batch_spec)

    def build_test_env(self, batch_spec: BatchSpec) -> list[dict]:
        """Build test environment (deprecated)."""
        return self.loader.load_split("test", batch_spec)

    def rollout(
        self,
        env_manager,  # actually list[dict] for route-effort
        skill_content: str,
        out_dir: str,
        **kwargs,
    ) -> list[dict]:
        """Run route-effort classification on items. Resume-aware."""
        items: list[dict] = env_manager  # type alias for clarity
        return run_batch(
            items=items,
            out_root=out_dir,
            skill_content=skill_content,
            exec_timeout=self.exec_timeout,
            workers=self.workers,
            max_completion_tokens=self.max_completion_tokens,
            diagnostic_mode=kwargs.get("diagnostic_mode", False),
            diagnostic_instruction=kwargs.get("diagnostic_instruction", ""),
            diagnostic_trace_context_by_id=kwargs.get("diagnostic_trace_context_by_id"),
            task_timeout=self.exec_timeout,
        )

    def get_task_types(self) -> list[str]:
        return ["classification"]
