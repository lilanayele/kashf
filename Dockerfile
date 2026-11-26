# Kashf demo image (Render free tier: 512 MB RAM). Needs NO Comtrade key at runtime.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg
WORKDIR /app

# dependencies first (cached layer); shap/pytest are not needed to serve the demo
COPY requirements.txt .
RUN grep -viE '^(shap|numba|llvmlite|slicer|cloudpickle|tqdm|pytest|iniconfig|pluggy|tomli|exceptiongroup)==' \
        requirements.txt > requirements-runtime.txt \
 && pip install -r requirements-runtime.txt

COPY . .
RUN pip install --no-deps -e . && sh scripts/build_demo.sh

EXPOSE 8800
CMD ["sh", "scripts/start.sh"]
