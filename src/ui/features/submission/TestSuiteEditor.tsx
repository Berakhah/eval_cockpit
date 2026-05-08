import { useState } from "react";
import type { TestFile, TestSuite } from "@/domain/submission";
import { Card } from "@/ui/components/Stat";
import { cn } from "@/lib/cn";

interface Props {
  value: TestSuite;
  onChange: (ts: TestSuite) => void;
}

export function TestSuiteEditor({ value, onChange }: Props) {
  const [activeFile, setActiveFile] = useState(0);

  const updateFile = (index: number, patch: Partial<TestFile>) => {
    const files = value.files.map((f, i) => (i === index ? { ...f, ...patch } : f));
    // Keep entrypoint in sync when the active file's name changes.
    const newEntrypoint =
      index === value.files.findIndex((f) => f.name === value.entrypoint)
        ? (patch.name ?? value.entrypoint)
        : value.entrypoint;
    onChange({ ...value, files, entrypoint: newEntrypoint });
  };

  const addFile = () => {
    const newFile: TestFile = { name: `test_${value.files.length + 1}.py`, content: "" };
    onChange({ ...value, files: [...value.files, newFile] });
    setActiveFile(value.files.length);
  };

  const removeFile = (index: number) => {
    if (value.files.length <= 1) return;
    const files = value.files.filter((_, i) => i !== index);
    const newActive = Math.min(activeFile, files.length - 1);
    const newEntrypoint =
      value.files[index].name === value.entrypoint
        ? files[0].name
        : value.entrypoint;
    setActiveFile(newActive);
    onChange({ ...value, files, entrypoint: newEntrypoint });
  };

  const file = value.files[activeFile] ?? value.files[0];
  if (!file) return null;

  return (
    <Card
      title="test suite"
      hint={
        <span className="text-[10px] font-mono text-muted-foreground">
          framework: <span className="text-foreground">{value.framework}</span>
        </span>
      }
      className="rounded-none border-0 border-b"
    >
      {/* File tabs */}
      <div className="flex items-center h-8 border-b border-border bg-surface-1 overflow-x-auto">
        {value.files.map((f, i) => (
          <button
            key={i}
            onClick={() => setActiveFile(i)}
            className={cn(
              "h-full px-3 text-[11px] font-mono shrink-0 flex items-center gap-1.5 border-r border-border transition-colors",
              i === activeFile
                ? "bg-background text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-surface-2",
              f.name === value.entrypoint && "font-semibold",
            )}
          >
            <span>{f.name || "untitled"}</span>
            {f.name === value.entrypoint && (
              <span className="text-[9px] text-primary">●</span>
            )}
            {value.files.length > 1 && (
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                onKeyDown={(e) => e.key === "Enter" && removeFile(i)}
                className="ml-0.5 text-muted-foreground hover:text-danger"
                aria-label={`remove ${f.name}`}
              >
                ×
              </span>
            )}
          </button>
        ))}
        <button
          onClick={addFile}
          className="h-full px-3 text-[11px] font-mono text-muted-foreground hover:text-primary shrink-0"
          aria-label="add file"
        >
          +
        </button>
      </div>

      {/* Active file editor */}
      <div className="divide-y divide-border">
        {/* File name + entrypoint toggle */}
        <div className="grid grid-cols-[1fr_auto] gap-px bg-border">
          <label className="bg-card flex flex-col gap-1 px-3 py-2">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              filename
            </span>
            <input
              value={file.name}
              onChange={(e) => updateFile(activeFile, { name: e.target.value })}
              className="bg-transparent outline-none text-xs font-mono text-foreground focus:text-primary"
              placeholder="test_add.py"
            />
          </label>
          <button
            onClick={() => onChange({ ...value, entrypoint: file.name })}
            className={cn(
              "bg-card px-3 text-[11px] font-mono transition-colors",
              file.name === value.entrypoint
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground",
            )}
            title="Set as entrypoint"
          >
            {file.name === value.entrypoint ? "entrypoint ●" : "set entrypoint"}
          </button>
        </div>

        {/* File content */}
        <div className="bg-card">
          <textarea
            value={file.content}
            onChange={(e) => updateFile(activeFile, { content: e.target.value })}
            className="w-full min-h-[180px] px-3 py-2 text-xs font-mono bg-transparent outline-none resize-y text-foreground focus:text-primary"
            placeholder="# test file content"
            spellCheck={false}
          />
        </div>
      </div>
    </Card>
  );
}
