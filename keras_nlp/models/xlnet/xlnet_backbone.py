# Copyright 2023 The KerasNLP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from keras_nlp.backend import keras
from keras_nlp.models.backbone import Backbone
from keras_nlp.models.xlnet.xlnet_content_and_query_embedding import (
    ContentAndQueryEmbedding,
)
from keras_nlp.models.xlnet.xlnet_encoder import XLNetAttentionMaskLayer
from keras_nlp.models.xlnet.xlnet_encoder import XLNetEncoder
from keras_nlp.models.xlnet.xlnet_encoder import XLNetSegmentMatrixLayer


@keras.saving.register_keras_serializable(package="keras_nlp")
class XLNetBackbone(Backbone):
    """XLNet encoder network.

    This class implements a XLNet Transformer.

    The default constructor gives a fully customizable, randomly initialized
    XLNet encoder with any number of layers, heads, and embedding dimensions.
    To load preset architectures and weights, use the `from_preset` constructor.

    Disclaimer: Pre-trained models are provided on an "as is" basis, without
    warranties or conditions of any kind.

    Attributes:
        vocabulary_size: int. The size of the token vocabulary.
        num_layers: int. The number of transformer encoder layers.
        num_heads: int, the number of heads in the
            `keras.layers.TwoStreamRelativeAttention` layer.
        hidden_dim: int, the size hidden states.
        intermediate_dim: int, the hidden size of feedforward network.
        dropout: float, defaults to 0.0 the dropout value, shared by
            `keras.layers.TwoStreamRelativeAttention` and feedforward network.
        activation: string or `keras.activations`, defaults to "gelu". the
            activation function of feedforward network.
        kernel_initializer_range: int, defaults to 0.02. The kernel initializer
            range for the dense and relative attention layers.
        bias_initializer: string or `keras.initializers` initializer,
            defaults to "zeros". The bias initializer for
            the dense and multiheaded relative attention layers.

    Call arguments:
        token_ids: Indices of input sequence tokens in the vocabulary of shape
            `[batch_size, sequence_length]`.
        segment_ids: Segment token indices to indicate first and second portions
            of the inputs of shape `[batch_size, sequence_length]`.
        padding_mask: Mask to avoid performing attention on padding token indices
            of shape `[batch_size, sequence_length]`.

    Examples:
    ```python
    import numpy as np
    from keras_nlp.models import XLNetBackbone

    input_data = {
        "token_ids": np.array(
            [460, 5272, 1758, 4905, 9, 4, 3], shape=(1, 7),
        ),
        "segment_ids": np.array(
            [0, 0, 0, 0, 0, 0, 2], shape=(1, 7),
        ),
        "padding_mask": np.array(
            [1, 1, 1, 1, 1, 1, 1], shape=(1, 7)
        ),
    }

    # Randomly initialized XLNet encoder with a custom config
    model = keras_nlp.models.XLNetBackbone(
        vocabulary_size=32000,
        num_layers=12,
        num_heads=12,
        hidden_dim=768,
        intermediate_dim=3072,
    )
    output = model(input_data)
    ```
    """

    def __init__(
        self,
        vocabulary_size,
        num_layers,
        num_heads,
        hidden_dim,
        intermediate_dim,
        dropout=0.0,
        activation="gelu",
        kernel_initializer_range=0.02,
        bias_initializer="zeros",
        **kwargs,
    ):
        # Inputs
        token_id_input = keras.Input(
            shape=(None,), dtype="int32", name="token_ids"
        )
        padding_mask = keras.Input(
            shape=(None,), dtype="int32", name="padding_mask"
        )
        segment_ids = keras.Input(
            shape=(None,), dtype="int32", name="segment_ids"
        )

        # Content and Query Embedding
        word_emb, pos_emb = ContentAndQueryEmbedding(
            vocabulary_size=vocabulary_size,
            hidden_dim=hidden_dim,
            dropout=dropout,
            name="content_query_embedding",
        )(token_id_input=token_id_input)

        # Apply XLNetAttentionMaskLayer and XLNetSegmentMatrixLayer Layers
        # to get the processed attention masks and segment matrix.
        attn_mask_content, attn_mask_query = XLNetAttentionMaskLayer(
            hidden_dim=hidden_dim,
            kernel_initializer_range=kernel_initializer_range,
            name="encoder_block_attn_mask_layer",
        )(padding_mask)
        seg_mat = XLNetSegmentMatrixLayer(name="encoder_block_seg_mat_layer")(
            segment_ids
        )

        output_content = word_emb

        # Encoders
        head_dim = hidden_dim // num_heads
        for i in range(num_layers):
            output_content, output_query = XLNetEncoder(
                num_heads=num_heads,
                hidden_dim=hidden_dim,
                head_dim=head_dim,
                intermediate_dim=intermediate_dim,
                dropout=dropout,
                activation=activation,
                layer_norm_epsilon=1e-12,
                kernel_initializer_range=kernel_initializer_range,
                bias_initializer=bias_initializer,
                name=f"xlnet_encoder_{i}",
            )(
                output_content=output_content,
                attn_mask_content=attn_mask_content,
                attn_mask_query=attn_mask_query,
                pos_emb=pos_emb,
                seg_mat=seg_mat,
            )

        output = keras.layers.Dropout(dropout)(output_content)

        super().__init__(
            inputs={
                "token_ids": token_id_input,
                "padding_mask": padding_mask,
                "segment_ids": segment_ids,
            },
            outputs=output,
            **kwargs,
        )

        # All references to `self` below this line
        self.vocabulary_size = vocabulary_size
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.hidden_dim = hidden_dim
        self.intermediate_dim = intermediate_dim
        self.dropout = dropout
        self.activation = activation
        self.kernel_initializer_range = kernel_initializer_range
        self.bias_initializer = bias_initializer

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "vocabulary_size": self.vocabulary_size,
                "num_layers": self.num_layers,
                "num_heads": self.num_heads,
                "hidden_dim": self.hidden_dim,
                "intermediate_dim": self.intermediate_dim,
                "dropout": self.dropout,
                "activation": self.activation,
                "kernel_initializer_range": self.kernel_initializer_range,
                "bias_initializer": self.bias_initializer,
            }
        )
        return config

    @property
    def token_embedding(self):
        return self.get_layer("content_query_embedding").word_embed
