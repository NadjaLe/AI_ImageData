#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 27 16:36:37 2021

@author: nadjalehmann
"""
import numpy as np
import tensorflow as tf

from tensorflow import keras
from tensorflow.keras import layers
from scipy import ndimage


import matplotlib.pyplot as plt
import random

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten, Conv3D, MaxPooling3D, Dropout
from tensorflow.keras.utils import to_categorical


AcD = np.load("file_name_AcD.npy",mmap_mode=None, allow_pickle=True , fix_imports=True, encoding='ASCII')
nonAcD = np.load("file_name_nonAcD.npy",mmap_mode=None, allow_pickle= True, fix_imports=True, encoding='ASCII')


AcD_label = np.array([1 for _ in range(len(AcD))])
nonAcD_label = np.array([0 for _ in range(len(nonAcD))])

# Split data in the ratio 70-30 for training and validation.
x_train = np.concatenate((AcD[:140], nonAcD[:140]), axis=0)
y_train = np.concatenate((AcD_label[:140], nonAcD_label [:140]), axis=0)
x_val = np.concatenate((AcD[140:], nonAcD[140:]), axis=0)
y_val = np.concatenate((AcD_label[140:], nonAcD_label[140:]), axis=0)



@tf.function
def rotate(volume):
    """Rotate the volume by a few degrees"""

    def scipy_rotate(volume):
        # define some rotation angles
        angles = [-20, -10, -5, 5, 10, 20]
        # pick angles at random
        angle = random.choice(angles)
        # rotate volume
        volume = ndimage.rotate(volume, angle, axes= (1,0), reshape=False)
        volume[volume < 0] = 0
        volume[volume > 1] = 1
        return volume

    augmented_volume = tf.numpy_function(scipy_rotate, [volume], tf.float32)
    return augmented_volume


def train_preprocessing(volume, label):
    """Process training data by rotating and adding a channel."""
    # Rotate volume
    volume = rotate(volume)
    return volume, label


# Define data loaders.
train_loader = tf.data.Dataset.from_tensor_slices((x_train, y_train))
validation_loader = tf.data.Dataset.from_tensor_slices((x_val, y_val))

batch_size = 2
# Augment the on the fly during training.
train_dataset = (
    train_loader.shuffle(len(x_train))
    .map(train_preprocessing)
    .batch(batch_size)
    .prefetch(2)
)
# Only rescale.
validation_dataset = (
    validation_loader.shuffle(len(x_val))
    #.map(validation_preprocessing)
    .batch(batch_size)
    .prefetch(2)
)


# data = train_dataset.take(1)
# images, labels = list(data)[0]
# images = images.numpy()
# image = images[0]
# print("Dimension of the scan is:", image.shape)
#plt.imshow(np.squeeze(image[:, :,: ]), cmap="Spectral")


def get_model(width=128, height=128, depth=15):
    """Build a 3D convolutional neural network model."""

    inputs = keras.Input((width, height, depth, 2))

    
    x = layers.Conv3D(filters=64, kernel_size=(3,3,3), activation="relu", kernel_initializer='he_uniform', padding = "same")(inputs)
    x = layers.MaxPool3D(pool_size=(2,2,2))(x)
    x = layers.BatchNormalization()(x)
    

    x = layers.Conv3D(filters=128, kernel_size=(3,3,3), activation="relu",kernel_initializer='he_uniform',padding = "same")(x)
    x = layers.MaxPool3D(pool_size=(2,2,2))(x)
    x = layers.BatchNormalization()(x)

    x = layers.Conv3D(filters=256, kernel_size=(3,3,3), activation="relu", kernel_initializer='he_uniform',padding = "same")(x)
    x = layers.MaxPool3D(pool_size=(2,2,2))(x)
    x = layers.BatchNormalization()(x)

    x = layers.GlobalAveragePooling3D()(x)
    x = layers.Dense(units=512, activation="relu")(x)
    x = layers.Dropout(0.3)(x)

    outputs = layers.Dense(units=1, activation="sigmoid")(x)

    # Define the model.
    model = keras.Model(inputs, outputs, name="3dcnn")
    return model


#Build model.
model = get_model(width=128, height=128, depth=15)
model.summary()

# # Compile model.
initial_learning_rate = 0.001
lr_schedule = keras.optimizers.schedules.ExponentialDecay(
    initial_learning_rate, decay_steps=100000, decay_rate=0.96, staircase=True
)
model.compile(
    loss="binary_crossentropy",
    optimizer=keras.optimizers.Adam(learning_rate=lr_schedule),
    metrics=["acc"],
)

# Define callbacks.
checkpoint_cb = keras.callbacks.ModelCheckpoint(
    "3d_image_classification.h5", save_best_only=True
)
#early_stopping_cb = keras.callbacks.EarlyStopping(monitor="val_acc", patience=15)

# Train the model, doing validation at the end of each epoch
epochs = 50
model.fit(
    train_dataset,
    validation_data=validation_dataset,
    epochs=epochs,
    shuffle=True,
    verbose=1,
    callbacks=[checkpoint_cb], #, early_stopping_cb
)


# Visualizing model performance

fig, ax = plt.subplots(1, 2, figsize=(20, 3))
ax = ax.ravel()

for i, metric in enumerate(["acc", "loss"]):
    ax[i].plot(model.history.history[metric])
    ax[i].plot(model.history.history["val_" + metric])
    ax[i].set_title("Model {}".format(metric))
    ax[i].set_xlabel("epochs")
    ax[i].set_ylabel(metric)
    ax[i].legend(["train", "val"])
