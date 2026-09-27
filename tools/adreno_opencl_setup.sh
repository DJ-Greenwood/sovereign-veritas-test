#!/data/data/com.termux/files/usr/bin/bash
# adreno_opencl_setup.sh - Termux on a Snapdragon phone: make llama.cpp's OpenCL backend reach
# Qualcomm's Adreno driver, and install a `llama-server-adreno` command that uses it.
#
# Why this is needed (docs/PLATFORM_TESTS.md, 2026-09-26): Android refuses to load /vendor/lib64
# libraries into an app ("not accessible for the namespace"), but /data is permitted. So the vendor
# OpenCL loader, Qualcomm's driver and the driver's runtime libraries are copied into ~/.adreno-cl
# and found through LD_LIBRARY_PATH. Nothing outside Termux's home and prefix is changed.
#
# Re-run after any system (ROM) update: the copied driver must match the phone's current one.
# Needs: pkg install llama-cpp llama-cpp-backend-opencl opencl-vendor-driver
#
#   bash tools/adreno_opencl_setup.sh
# Exit: 0 GPUOpenCL listed by llama-server | 1 not listed | 2 could not run (missing pieces)
set -u
D="$HOME/.adreno-cl"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
LOADER="$PREFIX/opt/vendor/lib/libOpenCL.so"

command -v llama-server >/dev/null || { echo "COULD NOT RUN: llama-server not found (pkg install llama-cpp)"; exit 2; }
[ -f "$LOADER" ] || { echo "COULD NOT RUN: $LOADER missing (pkg install opencl-vendor-driver)"; exit 2; }
[ -f /vendor/lib64/libOpenCL_adreno.so ] || { echo "COULD NOT RUN: no /vendor/lib64/libOpenCL_adreno.so (not an Adreno phone?)"; exit 2; }

mkdir -p "$D"
cp -f "$LOADER" "$D/libOpenCL.so"
for n in libOpenCL_adreno.so libadreno_utils.so libadreno_compiler_cl.so libgsl.so libllvm-qcom.so \
         libCB.so libadreno_app_profiles.so libq3dtools_adreno.so; do
    if [ -f "/vendor/lib64/$n" ]; then cp -f "/vendor/lib64/$n" "$D/"; else echo "note: /vendor/lib64/$n not present"; fi
done
# Never keep Android's own copies of these: they shadow Termux's and break llama.cpp's loading.
rm -f "$D/libc++.so" "$D/libbase.so" "$D/libcutils.so"
echo "copied into $D: $(cd "$D" && ls | tr '\n' ' ')"

W="$PREFIX/bin/llama-server-adreno"
cat > "$W" <<'WRAP'
#!/data/data/com.termux/files/usr/bin/sh
# llama-server on Qualcomm's OpenCL (Adreno) only; written by sovereign-veritas/tools/adreno_opencl_setup.sh.
# Every layer on the GPU. Vulkan is not used: on the S25 it silently corrupted output (docs/PLATFORM_TESTS.md).
LD_LIBRARY_PATH="$HOME/.adreno-cl${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec llama-server --device GPUOpenCL -ngl 99 "$@"
WRAP
chmod +x "$W"
echo "installed $W"

DEV=$(LD_LIBRARY_PATH="$D" llama-server --list-devices 2>&1 | grep -E "GPUOpenCL")
if [ -n "$DEV" ]; then
    echo "OK: $DEV"
    exit 0
fi
echo "NOT OK: llama-server does not list GPUOpenCL with $D"
exit 1
