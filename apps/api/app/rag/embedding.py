import hashlib
import math
from functools import lru_cache
from pathlib import Path
from typing import cast

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from fastembed.text.onnx_embedding import OnnxTextEmbedding
from tokenizers import Tokenizer

MODEL = "intfloat/multilingual-e5-small-q8"
MODEL_FILE = "onnx/model_qint8_avx512_vnni.onnx"


@lru_cache(maxsize=1)
def encoder() -> tuple[TextEmbedding, Tokenizer, str]:
    if MODEL not in {item["model"] for item in TextEmbedding.list_supported_models()}:
        TextEmbedding.add_custom_model(
            model=MODEL,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf="intfloat/multilingual-e5-small"),
            dim=384,
            model_file=MODEL_FILE,
            license="mit",
            size_in_gb=0.118,
        )
    model = TextEmbedding(MODEL, threads=2, providers=["CPUExecutionProvider"])
    backend = cast(OnnxTextEmbedding, model.model)
    if backend.tokenizer is None:
        raise ValueError("Tokenizer indisponível.")
    tokenizer = Tokenizer.from_str(backend.tokenizer.to_str())
    tokenizer.no_padding()
    tokenizer.no_truncation()
    with (Path(backend._model_dir) / MODEL_FILE).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return model, tokenizer, "e5-small-q8:" + digest


def embed(texts: list[str], *, query: bool = False) -> list[list[float]]:
    if not texts or len(texts) > 64:
        raise ValueError("Envie de 1 a 64 textos por lote.")
    model, tokenizer, _ = encoder()
    prefix = "query: " if query else "passage: "
    prepared = [prefix + value for value in texts]
    if any(not value.strip() for value in texts) or any(
        len(tokenizer.encode(value).ids) > 512 for value in prepared
    ):
        raise ValueError("Texto vazio ou acima da janela do encoder.")
    vectors = [vector.tolist() for vector in model.embed(prepared, batch_size=8)]
    if len(vectors) != len(texts) or any(
        len(vector) != 384
        or not all(math.isfinite(value) for value in vector)
        or math.isclose(sum(value * value for value in vector), 0)
        for vector in vectors
    ):
        raise ValueError("Embedding inválido.")
    return vectors
