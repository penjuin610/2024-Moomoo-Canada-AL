# moomoo User ID OCR Toolkit

[English](#english) | [中文](#中文)

---

## English

### Overview

This repository packages a local OCR workflow for extracting 8-digit `User ID`
values from moomoo account screenshots and mobile photos.

It is designed for high-volume local processing on macOS and supports workflows
that start from hundreds of screenshots and scale toward thousands or tens of
thousands of images through folder-based batch processing.

It is especially practical when source images come from iPhone photo exports
such as `.HEIC` files.

### Project Context

This project is part of my Python automation and operations portfolio related to
moomoo Canada workflows from 2024 to 2026. It demonstrates practical work in:

- local OCR pipelines
- image preprocessing for noisy mobile photos
- batch processing of large screenshot folders
- CSV export for downstream review and reconciliation
- notebook-based operational tooling for non-engineering users

### Features

- Extracts 8-digit `User ID` values from single images or full folders
- Supports large folder-based review workflows for hundreds to tens of thousands of images
- Supports `.jpg`, `.png`, `.tiff`, `.webp`, `.heic`, and `.heif`
- Uses macOS native Vision OCR as the primary recognition backend
- Automatically converts `HEIC/HEIF` to temporary PNG on macOS using `sips`
- Supports `fast` and `accurate` OCR modes
- Can retry only failed images with a second accurate pass
- Prints live progress updates with percentage, elapsed time, and ETA
- Runs parallel folder processing with configurable worker count
- Exports CSV with success and failure file tracking
- Includes both a Python script and a Jupyter notebook workflow

### Repository Files

- `extract_moomoo_id.py`: local CLI script for single-image or batch-folder OCR
- `moomoo_user_id_batch.ipynb`: notebook version for VS Code / Jupyter workflows
- `requirements.txt`: minimal Python dependency list

### Requirements

- Python 3.10+
- macOS with Vision framework support
- `clang` available in `PATH` for the local Vision helper build
- macOS `sips` for `.heic` / `.heif` conversion

Install Python dependency:

```bash
pip install -r requirements.txt
```

### CLI Usage

Single image:

```bash
python3 extract_moomoo_id.py /path/to/photo.jpg --json
```

Batch folder:

```bash
python3 extract_moomoo_id.py /path/to/photo_folder --csv-output moomoo_user_ids.csv --mode fast --workers 6 --retry-failed-with-accurate
```

Recommended for large batches:

- Start with `--mode fast`
- Use `--workers 4`, `6`, or `8` depending on machine performance
- Add `--retry-failed-with-accurate` to improve recall only for failed images

### Notebook Usage

Open `moomoo_user_id_batch.ipynb` in VS Code or Jupyter and run:

1. the folder preview cell to confirm image count and filenames
2. the extraction cell to generate the CSV report

### CSV Output

The generated CSV contains:

- `file_name`
- `user_id`
- `success_photo_name`
- `failed_photo_name`
- `status`
- `failed_reason`
- `top_candidates`

### Recommended Failed-Image Workflow

For large real-world batches, the most practical workflow is:

1. run a full folder pass with `--mode fast`
2. review the CSV and inspect rows where `status=failed`
3. rerun only failed images with:

```bash
python3 extract_moomoo_id.py /path/to/photo_folder \
  --csv-output moomoo_user_ids_failed_rerun.csv \
  --mode accurate \
  --workers 3 \
  --only-failed-from-csv moomoo_user_ids.csv
```

This keeps the first pass fast while spending more OCR time only on difficult images.

### Professional Notes

- This repository is intended as a portfolio demonstration of real-world Python automation work.
- It is a local utility project and is not an official moomoo repository.
- No private production data, credentials, or internal business logic are included here.
- For very large image sets, actual throughput depends on local machine performance, storage speed, and OCR workload quality.

---

## 中文

### 项目简介

这个仓库整理了一个本地 OCR 工具链，用来从 moomoo 账户截图和手机拍照中提取
8 位 `User ID`。

它适合在 macOS 本地批量处理图片，既可以处理几百张，也适合扩展到几千张、上万张
的文件夹批处理场景。

尤其适合 iPhone 导出的 `.HEIC` 照片。

### 项目背景

这个项目是我 2024 到 2026 年与 moomoo Canada 相关 Python 自动化与运营支持工作
的一部分作品集整理，主要体现了这些能力：

- 本地 OCR 流程搭建
- 面向手机噪声照片的图像预处理
- 大批量截图/照片文件夹批处理
- 面向复核流程的 CSV 导出
- 方便非工程同事使用的 notebook 工具化

### 功能特性

- 支持单张图片或整个文件夹批量提取 8 位 `User ID`
- 支持面向几百、几千、上万张图片的文件夹批处理工作流
- 支持 `.jpg`、`.png`、`.tiff`、`.webp`、`.heic`、`.heif`
- 主识别后端改为 macOS 原生 Vision OCR
- 在 macOS 下自动用 `sips` 将 `HEIC/HEIF` 转成临时 PNG
- 支持 `fast` 和 `accurate` 两种 OCR 模式
- 支持只对失败图片做第二轮 `accurate` 重试
- 运行时实时输出百分比、耗时和预计剩余时间 ETA
- 支持可配置并行 worker 数量
- 输出带成功/失败文件名记录的 CSV
- 同时提供 Python 脚本版本和 Jupyter Notebook 版本

### 仓库文件说明

- `extract_moomoo_id.py`：命令行批处理脚本
- `moomoo_user_id_batch.ipynb`：适合 VS Code / Jupyter 的 notebook 工作流
- `requirements.txt`：最小 Python 依赖

### 运行要求

- Python 3.10+
- 支持 Vision.framework 的 macOS 环境
- 可在 `PATH` 中使用的 `clang`
- macOS 自带 `sips`，用于处理 `.heic` / `.heif`

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

### 命令行使用方式

单图提取：

```bash
python3 extract_moomoo_id.py /path/to/photo.jpg --json
```

批量提取：

```bash
python3 extract_moomoo_id.py /path/to/photo_folder --csv-output moomoo_user_ids.csv --mode fast --workers 6 --retry-failed-with-accurate
```

大批量图片推荐参数：

- 优先从 `--mode fast` 开始
- 根据机器性能使用 `--workers 4`、`6` 或 `8`
- 如果想兼顾速度和命中率，可以加 `--retry-failed-with-accurate`

### Notebook 使用方式

在 VS Code 或 Jupyter 中打开 `moomoo_user_id_batch.ipynb`，按顺序运行：

1. 先运行文件夹预览 cell，确认照片数量和文件名
2. 再运行提取 cell，生成 CSV

### CSV 输出字段

生成的 CSV 包含：

- `file_name`
- `user_id`
- `success_photo_name`
- `failed_photo_name`
- `status`
- `failed_reason`
- `top_candidates`

### failed 图片推荐处理流程

比较实用的真实工作流是：

1. 先用 `--mode fast` 全量跑一轮
2. 查看 CSV 中 `status=failed` 的记录
3. 只对 failed 图片再跑一次：

```bash
python3 extract_moomoo_id.py /path/to/photo_folder \
  --csv-output moomoo_user_ids_failed_rerun.csv \
  --mode accurate \
  --workers 3 \
  --only-failed-from-csv moomoo_user_ids.csv
```

这样第一轮保持速度，第二轮只把 OCR 计算量花在难图上。

### 专业说明

- 这个仓库用于展示我在真实业务场景中的 Python 自动化能力。
- 这是一个本地工具型作品集项目，不是 moomoo 官方仓库。
- 仓库中不包含任何私有生产数据、账号凭证或内部业务逻辑。
- 如果图片量非常大，实际处理速度会取决于本机性能、磁盘速度以及图片质量.
