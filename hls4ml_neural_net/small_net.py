"""
Small Neural Network with HLS4ML
=================================
Builds a tiny 3-layer classifier, trains it on synthetic data,
then converts it to HLS C++ firmware with hls4ml.
"""

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import hls4ml

# ── Reproducibility ──────────────────────────────────────────────────────────
tf.random.set_seed(42)
np.random.seed(42)

# ── 1. Synthetic dataset (4-feature, 3-class) ────────────────────────────────
N_SAMPLES = 1000
N_FEATURES = 4
N_CLASSES = 3

X = np.random.randn(N_SAMPLES, N_FEATURES).astype(np.float32)
y = (np.sum(X, axis=1) > 0).astype(int)          # binary baseline
# promote to 3-class by splitting the positive region
y = np.where(X[:, 0] > 0.5, 2, y).astype(int)
Y = keras.utils.to_categorical(y, N_CLASSES)

split = int(0.8 * N_SAMPLES)
X_train, X_test = X[:split], X[split:]
Y_train, Y_test = Y[:split], Y[split:]

# ── 2. Define a tiny Keras model ─────────────────────────────────────────────
#   Input(4) → Dense(16, ReLU) → Dense(8, ReLU) → Dense(3, Softmax)
model = keras.Sequential(
    [
        keras.Input(shape=(N_FEATURES,), name="data_in"),
        layers.Dense(16, activation="relu", name="dense_0"),
        layers.Dense(8, activation="relu", name="dense_1"),
        layers.Dense(N_CLASSES, activation="softmax", name="output"),
    ],
    name="small_net",
)

model.summary()

# ── 3. Train ──────────────────────────────────────────────────────────────────
model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"],
)

history = model.fit(
    X_train, Y_train,
    validation_data=(X_test, Y_test),
    epochs=30,
    batch_size=32,
    verbose=1,
)

loss, acc = model.evaluate(X_test, Y_test, verbose=0)
print(f"\nTest accuracy: {acc:.4f}")

# ── 4. Configure hls4ml ───────────────────────────────────────────────────────
#   ap_fixed<16,6> gives 16-bit fixed-point with 6 integer bits.
#   ReuseFactor=1 → fully unrolled (smallest latency, larger area).
hls_config = hls4ml.utils.config_from_keras_model(
    model,
    granularity="name",         # per-layer configuration
    default_precision="ap_fixed<16,6>",
    default_reuse_factor=1,
)

# Optional: tighten precision on the output softmax layer
hls_config["LayerName"]["output"]["Precision"]["result"] = "ap_fixed<16,6>"

print("\nhls4ml layer config:")
for layer, cfg in hls_config["LayerName"].items():
    print(f"  {layer}: {cfg}")

# ── 5. Convert to HLS project ─────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "hls_project")

hls_model = hls4ml.converters.convert_from_keras_model(
    model,
    hls_config=hls_config,
    output_dir=OUTPUT_DIR,
    backend="Vivado",       # generates Vivado HLS / Vitis HLS C++
    io_type="io_parallel",  # all inputs arrive simultaneously
    part="xc7z020clg400-1", # Zynq-7020 (common dev board)
    clock_period=10,        # 10 ns → 100 MHz
)

# ── 6. Compile the HLS C-simulation model ─────────────────────────────────────
print("\nCompiling HLS C-simulation model …")
hls_model.compile()

# ── 7. Run bit-accurate C-simulation and compare to Keras ────────────────────
print("Running C-simulation on test set …")
y_keras = model.predict(X_test, verbose=0)
y_hls   = hls_model.predict(X_test)

# Accuracy of the HLS model
hls_pred_classes  = np.argmax(y_hls,   axis=1)
keras_pred_classes = np.argmax(y_keras, axis=1)
true_classes       = np.argmax(Y_test,  axis=1)

hls_acc   = np.mean(hls_pred_classes  == true_classes)
keras_acc = np.mean(keras_pred_classes == true_classes)
match_pct = np.mean(hls_pred_classes  == keras_pred_classes) * 100

print(f"\nKeras accuracy  : {keras_acc:.4f}")
print(f"HLS   accuracy  : {hls_acc:.4f}")
print(f"Keras↔HLS match : {match_pct:.1f}%")

# ── 8. Resource / timing report (no synthesis tool required) ─────────────────
print("\nHLS project written to:", os.path.abspath(OUTPUT_DIR))
print("Key files:")
for root, dirs, files in os.walk(OUTPUT_DIR):
    # Only show top-level and firmware/ directory
    depth = root.replace(OUTPUT_DIR, "").count(os.sep)
    if depth <= 1:
        indent = "  " * depth
        print(f"{indent}{os.path.basename(root)}/")
        for f in files:
            print(f"{indent}  {f}")
