import pytorch_lightning as pl
import torch
import torch.nn.functional as F
import torchmetrics
from torch import nn
from torch.optim.lr_scheduler import ReduceLROnPlateau


class Conv1dTextClassifier(pl.LightningModule):
    def __init__(
        self,
        vocab_size: int,
        max_tokens: int = 128,
        embed_len: int = 128,
        nfeatures: int = 64,
        num_classes: int = 2,
        lr_scheduler_patience: int = 2,
        class_weights: list = [],
    ):
        self.vocab_size = vocab_size
        self.max_tokens = max_tokens
        self.embed_len = embed_len
        self.nfeatures = nfeatures
        self.num_classes = num_classes
        self.lr = 1e-3
        self.lr_scheduler_patience = lr_scheduler_patience
        self.class_weights = class_weights

        super().__init__()
        self.save_hyperparameters()

        # layers
        self.embedding_layer = nn.Embedding(
            num_embeddings=self.vocab_size,
            embedding_dim=self.embed_len,
        )
        self.conv1 = nn.Conv1d(self.embed_len, 64, kernel_size=7, padding="same")
        self.conv2 = nn.Conv1d(64, 32, kernel_size=7, padding="same")
        self.pooling = nn.MaxPool1d(2)

        self.linear1 = nn.Linear(32, 32)
        self.linear2 = nn.Linear(32, self.num_classes)
        # self.linear = nn.Linear(self.nfeatures, self.num_classes)

        if len(self.class_weights):
            self.class_weights = torch.tensor(class_weights, dtype=torch.float32)

        self.logsoftmax = nn.LogSoftmax(dim=1)
        self.loss = nn.NLLLoss(weight=self.class_weights)

        # metrics
        self.accuracy = torchmetrics.Accuracy(
            task="multiclass",
            num_classes=self.num_classes,
        )
        self.f1score = torchmetrics.F1Score(
            task="multiclass",
            num_classes=self.num_classes,
        )

    def forward(self, X_batch):
        x = self.embedding_layer(X_batch)
        x = x.reshape(
            len(x), self.embed_len, self.max_tokens
        )  ## Embedding Length needs to be treated as channel dimension
        x = F.relu(self.conv1(x))
        x = self.pooling(x)
        # x = F.dropout(x, 0.5)
        x = F.relu(self.conv2(x))
        x, _ = x.max(dim=-1)

        x = self.linear2(x)
        x = self.logsoftmax(x)

        return x

    def predict_step(self, batch, batch_idx):
        return self(batch)

    def training_step(self, batch, batch_idx):
        # training_step defines the train loop.
        x, y = batch

        y_pred = self.forward(x)

        loss = self.loss(y_pred, y)
        acc = self.accuracy(y_pred, y)
        f1score = self.f1score(y_pred, y)

        self.log("loss", loss, on_epoch=True, prog_bar=True, logger=True)
        self.log("acc", acc, on_epoch=True, prog_bar=True, logger=True)
        self.log("f1score", f1score, on_epoch=True, prog_bar=True, logger=True)
        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch

        y_pred = self.forward(x)

        # loss = F.cross_entropy(y_pred, y)
        loss = self.loss(y_pred, y)
        acc = self.accuracy(y_pred, y)
        f1score = self.f1score(y_pred, y)

        self.log("val_loss", loss, on_epoch=True, prog_bar=True, logger=True)
        self.log("val_acc", acc, on_epoch=True, prog_bar=True, logger=True)
        self.log("val_f1score", f1score, on_epoch=True, prog_bar=True, logger=True)

    def test_step(self, batch, batch_idx):
        x, y = batch

        y_pred = self.forward(x)

        # loss = F.cross_entropy(y_pred, y)
        loss = self.loss(y_pred, y)
        acc = self.accuracy(y_pred, y)
        f1score = self.f1score(y_pred, y)

        self.log("test_loss", loss, on_epoch=True, prog_bar=True, logger=True)
        self.log("test_acc", acc, on_epoch=True, prog_bar=True, logger=True)
        self.log("test_f1score", f1score, on_epoch=True, prog_bar=True, logger=True)

    def configure_optimizers(self):
        # optimizer = torch.optim.Adam(self.parameters(), lr=1e-3)
        optimizer = torch.optim.AdamW(self.parameters(), lr=self.lr)
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": ReduceLROnPlateau(
                    optimizer,
                    patience=self.lr_scheduler_patience,
                ),
                "monitor": "val_loss",
                "frequency": 1,
                # If "monitor" references validation metrics, then "frequency" should be set to a
                # multiple of "trainer.check_val_every_n_epoch".
            },
        }
