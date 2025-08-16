import os
import json
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Constants
WORKSPACE_ROOT = Path("/workspace/anycode")
JOBS_DIR = WORKSPACE_ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="AnyCode Generator API", version="0.1.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


class GenerateRequest(BaseModel):
  instruction: str = Field(..., description="High-level description of what to build")
  language: Optional[str] = Field(None, description="Target programming language, e.g. python, typescript, go")
  framework: Optional[str] = Field(None, description="Optional framework preference, e.g. fastapi, express, react")
  filename: Optional[str] = Field(None, description="Suggested filename to use when saving the code")
  temperature: float = Field(0.2, ge=0.0, le=1.0, description="Sampling temperature for the LLM")


class GeneratedCode(BaseModel):
  code: str
  language: Optional[str] = None
  filename: Optional[str] = None
  model: Optional[str] = None


class SaveRequest(BaseModel):
  code: str
  filename: str
  job_id: Optional[str] = None


class JobInfo(BaseModel):
  job_id: str
  files: List[str]
  created_at: float


class JobsList(BaseModel):
  jobs: List[JobInfo]


def _get_openai_client() -> Optional[Any]:
  api_key = os.getenv("OPENAI_API_KEY")
  if not api_key:
    return None
  try:
    # Lazy import to keep startup fast if not installed
    from openai import OpenAI  # type: ignore
    base_url = os.getenv("OPENAI_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    return client
  except Exception:
    return None


def _build_system_prompt() -> str:
  return (
    "You are AnyCode, an expert code generation system. \n"
    "Requirements: output ONLY valid JSON with keys: filename, language, code. \n"
    "Do not include markdown code fences. Do not include commentary. \n"
    "The code should be idiomatic, well-structured, and runnable as-is. \n"
    "Prefer clear naming, guard clauses, minimal dependencies, and include necessary imports."
  )


def _build_user_prompt(req: GenerateRequest) -> str:
  lang_hint = f"Target language: {req.language}." if req.language else ""
  fw_hint = f" Framework: {req.framework}." if req.framework else ""
  filename_hint = f" Suggested filename: {req.filename}." if req.filename else ""
  return (
    f"Instruction: {req.instruction}\n"
    f"{lang_hint}{fw_hint}{filename_hint}\n"
    "Respond with JSON: {\"filename\": string, \"language\": string, \"code\": string}."
  )


def _fallback_code(req: GenerateRequest) -> GeneratedCode:
  language = (req.language or "python").lower()
  filename = req.filename
  code: str

  examples: Dict[str, Dict[str, str]] = {
    "python": {
      "filename": filename or "hello.py",
      "code": (
        "def greet(name: str) -> str:\n"
        "    return f'Hello, {name}!'\n\n"
        "if __name__ == '__main__':\n"
        "    print(greet('world'))\n"
      ),
    },
    "typescript": {
      "filename": filename or "hello.ts",
      "code": (
        "export function greet(name: string): string {\n"
        "  return `Hello, ${name}!`;\n"
        "}\n\n"
        "console.log(greet('world'));\n"
      ),
    },
    "javascript": {
      "filename": filename or "hello.js",
      "code": (
        "function greet(name) {\n"
        "  return `Hello, ${name}!`;\n"
        "}\n\n"
        "console.log(greet('world'));\n"
      ),
    },
    "go": {
      "filename": filename or "hello.go",
      "code": (
        "package main\n\nimport \"fmt\"\n\nfunc greet(name string) string {\n"
        "    return fmt.Sprintf(\"Hello, %s!\", name)\n}\n\nfunc main() {\n"
        "    fmt.Println(greet(\"world\"))\n}\n"
      ),
    },
  }

  picked = examples.get(language, examples["python"])
  return GeneratedCode(code=picked["code"], language=language, filename=picked["filename"], model="fallback")


@app.get("/healthz")
async def healthz() -> Dict[str, str]:
  return {"status": "ok"}


@app.post("/api/generate", response_model=GeneratedCode)
async def generate_code(req: GenerateRequest) -> GeneratedCode:
  client = _get_openai_client()
  if client is None:
    return _fallback_code(req)

  system_prompt = _build_system_prompt()
  user_prompt = _build_user_prompt(req)

  try:
    completion = client.chat.completions.create(
      model=DEFAULT_MODEL,
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
      ],
      temperature=req.temperature,
    )
    content = completion.choices[0].message.content or ""
  except Exception as e:
    # Use fallback on model error as well
    return _fallback_code(req)

  try:
    data = json.loads(content)
    filename = data.get("filename")
    language = data.get("language")
    code = data.get("code")
    if not isinstance(code, str):
      raise ValueError("Missing code field")
    return GeneratedCode(code=code, language=language, filename=filename, model=DEFAULT_MODEL)
  except Exception:
    # If model ignored JSON instruction, try to strip fences heuristically
    cleaned = content.strip()
    if cleaned.startswith("```"):
      parts = cleaned.split("\n", 1)
      if len(parts) == 2:
        maybe_lang_line, rest = parts[0], parts[1]
        if rest.endswith("```"):
          rest = rest[:-3]
        return GeneratedCode(code=rest.strip(), language=req.language, filename=req.filename, model=DEFAULT_MODEL)
    return GeneratedCode(code=cleaned, language=req.language, filename=req.filename, model=DEFAULT_MODEL)


@app.post("/api/save", response_model=JobInfo)
async def save_code(req: SaveRequest) -> JobInfo:
  job_id = req.job_id or f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
  job_dir = JOBS_DIR / job_id
  job_dir.mkdir(parents=True, exist_ok=True)

  # Normalize filename
  safe_filename = req.filename.strip().replace("..", "").replace("/", "_")
  target = job_dir / safe_filename
  target.write_text(req.code)

  metadata = {
    "created_at": time.time(),
    "files": [safe_filename],
  }
  (job_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

  return JobInfo(job_id=job_id, files=[safe_filename], created_at=metadata["created_at"])


@app.get("/api/jobs", response_model=JobsList)
async def list_jobs() -> JobsList:
  jobs: List[JobInfo] = []
  for child in JOBS_DIR.iterdir():
    if child.is_dir():
      meta_path = child / "metadata.json"
      created_at = child.stat().st_mtime
      files: List[str] = []
      if meta_path.exists():
        try:
          meta = json.loads(meta_path.read_text())
          files = list(meta.get("files", []))
          created_at = float(meta.get("created_at", created_at))
        except Exception:
          pass
      else:
        files = [p.name for p in child.glob("*.*")]
      jobs.append(JobInfo(job_id=child.name, files=files, created_at=created_at))
  jobs.sort(key=lambda j: j.created_at, reverse=True)
  return JobsList(jobs=jobs)


class FileSpec(BaseModel):
  filename: str
  code: str
  language: Optional[str] = None
  purpose: Optional[str] = None


class MultiGenerateRequest(GenerateRequest):
  num_files: Optional[int] = Field(None, ge=1, le=20)


class MultiGenerated(BaseModel):
  files: List[FileSpec]
  model: Optional[str] = None


class SaveMultiRequest(BaseModel):
  files: List[FileSpec]
  job_id: Optional[str] = None


def _build_system_prompt_multi() -> str:
  return (
    "You are AnyCode, an expert software architect and code generator.\n"
    "Output ONLY a valid JSON array where each item is an object with keys: \n"
    "filename (string), language (string), purpose (string), code (string).\n"
    "Do not include markdown fences or commentary.\n"
    "Generate minimal yet complete files that work together. Include imports."
  )


def _build_user_prompt_multi(req: MultiGenerateRequest) -> str:
  lang_hint = f"Target language: {req.language}." if req.language else ""
  fw_hint = f" Framework: {req.framework}." if req.framework else ""
  filename_hint = f" Prefer entry file named: {req.filename}." if req.filename else ""
  num_hint = f" Aim for about {req.num_files} files." if req.num_files else ""
  return (
    f"Project instruction: {req.instruction}\n"
    f"{lang_hint}{fw_hint}{filename_hint}{num_hint}\n"
    "Respond with a JSON array of files."
  )


@app.post("/api/generate_multi", response_model=MultiGenerated)
async def generate_code_multi(req: MultiGenerateRequest) -> MultiGenerated:
  client = _get_openai_client()
  if client is None:
    # Fallback: single-file from the single generator
    single = _fallback_code(req)
    return MultiGenerated(files=[FileSpec(filename=single.filename or "main", code=single.code, language=single.language)], model="fallback")

  try:
    completion = client.chat.completions.create(
      model=DEFAULT_MODEL,
      messages=[
        {"role": "system", "content": _build_system_prompt_multi()},
        {"role": "user", "content": _build_user_prompt_multi(req)},
      ],
      temperature=req.temperature,
    )
    content = completion.choices[0].message.content or ""
  except Exception:
    single = _fallback_code(req)
    return MultiGenerated(files=[FileSpec(filename=single.filename or "main", code=single.code, language=single.language)], model="fallback")

  cleaned = content.strip()
  if cleaned.startswith("```"):
    parts = cleaned.split("\n", 1)
    if len(parts) == 2:
      cleaned = parts[1]
    if cleaned.endswith("```"):
      cleaned = cleaned[:-3]
  try:
    payload = json.loads(cleaned)
    files: List[FileSpec] = []
    if isinstance(payload, list):
      for item in payload:
        if isinstance(item, dict) and "code" in item and "filename" in item:
          files.append(FileSpec(
            filename=str(item.get("filename")),
            code=str(item.get("code")),
            language=(item.get("language") or req.language),
            purpose=(item.get("purpose")),
          ))
    if not files:
      raise ValueError("No files parsed")
    return MultiGenerated(files=files, model=DEFAULT_MODEL)
  except Exception:
    single = _fallback_code(req)
    return MultiGenerated(files=[FileSpec(filename=single.filename or "main", code=single.code, language=single.language)], model=DEFAULT_MODEL)


@app.post("/api/save_multi", response_model=JobInfo)
async def save_code_multi(req: SaveMultiRequest) -> JobInfo:
  job_id = req.job_id or f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
  job_dir = JOBS_DIR / job_id
  job_dir.mkdir(parents=True, exist_ok=True)

  saved_files: List[str] = []
  for f in req.files:
    safe_filename = f.filename.strip().replace("..", "").replace("/", "_")
    target = job_dir / safe_filename
    target.write_text(f.code)
    saved_files.append(safe_filename)

  metadata = {
    "created_at": time.time(),
    "files": saved_files,
  }
  (job_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

  return JobInfo(job_id=job_id, files=saved_files, created_at=metadata["created_at"])


# ZIP download for a job
from fastapi.responses import Response  # noqa: E402
import io  # noqa: E402
import zipfile  # noqa: E402


@app.get("/api/jobs/{job_id}/zip")
async def download_job_zip(job_id: str):
  job_dir = JOBS_DIR / job_id
  if not job_dir.exists() or not job_dir.is_dir():
    raise HTTPException(status_code=404, detail="Job not found")

  buffer = io.BytesIO()
  with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in job_dir.glob("*"):
      if path.name == "metadata.json":
        continue
      if path.is_file():
        zf.writestr(path.name, path.read_text())
  buffer.seek(0)
  headers = {"Content-Disposition": f"attachment; filename=anycode-{job_id}.zip"}
  return Response(content=buffer.getvalue(), media_type="application/zip", headers=headers)