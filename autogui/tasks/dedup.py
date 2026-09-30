# -*- coding: utf-8 -*-
"""Task deduplication via sentence embedding cosine similarity.

Maintains a per-OS task registry. Before generating a new task,
checks whether a semantically similar task already exists.

Model: paraphrase-multilingual-MiniLM-L12-v2 (multilingual).
"""

import json
import threading
import numpy as np
from pathlib import Path
from autogui.utils.jsonio import atomic_write_json

_MODEL = None
_MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
_MODEL_LOCK = threading.Lock()
_REGISTRY_LOCK = threading.RLock()


def _load_model():
    """Lazy-load the sentence transformer model."""
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer(_MODEL_NAME)
    return _MODEL


def _cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return dot / norm if norm > 0 else 0.0


class TaskRegistry:
    """Per-OS task registry with embedding-based dedup.

    Stores task descriptions and their embeddings in a JSON file.
    """

    def __init__(self, registry_path=None):
        """
        Args:
            registry_path: Path to the JSON registry file. Pass None for an
                in-memory registry that never touches disk (used for per-seed
                dedup, where the pool must be scoped to one seed's trajectories
                and not accumulate across seeds or runs).
        """
        self.path = Path(registry_path) if registry_path is not None else None
        self._tasks = []
        self._embeddings = []
        self._load()

    def _load(self):
        """Load existing registry from disk (no-op for in-memory registries)."""
        if self.path is not None and self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Task registry must be an object')
            tasks, embeddings = data.get('tasks'), data.get('embeddings')
            if not isinstance(tasks, list) or not isinstance(embeddings, list) or len(tasks) != len(embeddings):
                raise ValueError('Invalid task registry')
            vectors = [np.asarray(e, dtype=float) for e in embeddings]
            if any(not isinstance(t, str) for t in tasks) or any(v.ndim != 1 or not v.size or not np.isfinite(v).all() for v in vectors):
                raise ValueError('Invalid task registry contents')
            if len({v.size for v in vectors}) > 1:
                raise ValueError('Inconsistent embedding dimensions')
            self._tasks, self._embeddings = tasks, vectors

    def _save(self):
        """Persist registry to disk (no-op for in-memory registries)."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'tasks': self._tasks,
            'embeddings': [e.tolist() for e in self._embeddings],
        }
        atomic_write_json(self.path, data)

    def check_duplicate(self, task_description, threshold=0.85):
        """Check if a task is too similar to existing ones.

        Args:
            task_description: The new task description
            threshold: Cosine similarity threshold (0-1). Above this = duplicate.

        Returns:
            (is_duplicate: bool, most_similar: str|None, similarity: float)
        """
        if not 0 <= threshold <= 1:
            raise ValueError('Dedup threshold must be between 0 and 1')
        with _REGISTRY_LOCK:
            self._load()
            tasks, embeddings = list(self._tasks), list(self._embeddings)
        if not tasks:
            return False, None, 0.0

        model = _load_model()
        new_embedding = np.asarray(model.encode(task_description), dtype=float)
        if new_embedding.ndim != 1 or not np.isfinite(new_embedding).all() or any(e.shape != new_embedding.shape for e in embeddings):
            raise ValueError('Invalid or incompatible task embedding')

        max_sim = 0.0
        most_similar = None
        for i, existing_emb in enumerate(embeddings):
            sim = _cosine_similarity(new_embedding, existing_emb)
            if sim > max_sim:
                max_sim = sim
                most_similar = tasks[i]

        is_dup = max_sim >= threshold
        return is_dup, most_similar, max_sim

    def add_task(self, task_description):
        """Add a task to the registry (after successful generation).

        Args:
            task_description: Task description string
        """
        model = _load_model()
        embedding = np.asarray(model.encode(task_description), dtype=float)
        if embedding.ndim != 1 or not embedding.size or not np.isfinite(embedding).all():
            raise ValueError('Invalid task embedding')
        with _REGISTRY_LOCK:
            self._load()
            if task_description in self._tasks:
                return
            if self._embeddings and self._embeddings[0].shape != embedding.shape:
                raise ValueError('Embedding dimensions differ from the saved registry')
            self._tasks.append(task_description)
            self._embeddings.append(embedding)
            self._save()

    @property
    def count(self):
        return len(self._tasks)

    @property
    def tasks(self):
        return list(self._tasks)


def get_registry_for_os(os_key):
    """Get or create a TaskRegistry for a specific OS.

    Registry is stored at: data/task_registries/{os_key}.json
    """
    from autogui.storage.manager import task_registry_path
    return TaskRegistry(task_registry_path(os_key))
