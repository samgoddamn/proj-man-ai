"use client";

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/useRequireAuth";
import type { Task, TaskStatus } from "@/lib/types";
import { Card } from "@/components/ui/primitives";

const COLUMNS: { key: TaskStatus; label: string }[] = [
  { key: "backlog", label: "Backlog" },
  { key: "todo", label: "Todo" },
  { key: "in_progress", label: "In Progress" },
  { key: "review", label: "Review" },
  { key: "done", label: "Done" },
];

function TaskCard({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: task.id });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={
        "cursor-grab rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-900 " +
        (isDragging ? "opacity-40" : "")
      }
    >
      <div className="font-medium">{task.title}</div>
      <div className="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 dark:bg-slate-800">{task.type}</span>
        {task.estimate != null && <span>{task.estimate}p</span>}
      </div>
    </div>
  );
}

function Column({ col, tasks }: { col: { key: TaskStatus; label: string }; tasks: Task[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key });
  return (
    <div
      ref={setNodeRef}
      className={
        "flex w-64 shrink-0 flex-col gap-2 rounded-lg bg-slate-100 p-3 dark:bg-slate-800/80 " +
        (isOver ? "ring-2 ring-brand-400" : "")
      }
    >
      <div className="flex items-center justify-between text-sm font-semibold text-slate-700 dark:text-slate-200">
        <span>{col.label}</span>
        <span className="text-slate-400 dark:text-slate-500">{tasks.length}</span>
      </div>
      {tasks.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}
    </div>
  );
}

export default function KanbanPage() {
  const ready = useRequireAuth();
  const { id } = useParams<{ id: string }>();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [active, setActive] = useState<Task | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  useEffect(() => {
    if (!ready) return;
    api
      .getBoard(id)
      .then((b) => setTasks(b.columns.flatMap((c) => c.tasks)))
      .catch((e) => setError(String(e)));
  }, [ready, id]);

  function onDragStart(e: DragStartEvent) {
    setActive(tasks.find((t) => t.id === e.active.id) ?? null);
  }

  async function onDragEnd(e: DragEndEvent) {
    setActive(null);
    const taskId = String(e.active.id);
    const newStatus = e.over?.id as TaskStatus | undefined;
    const task = tasks.find((t) => t.id === taskId);
    if (!task || !newStatus || task.status === newStatus) return;

    // Optimistisk uppdatering; rulla tillbaka vid fel.
    const prev = task.status;
    setTasks((ts) => ts.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)));
    try {
      await api.patchTask(taskId, { status: newStatus });
    } catch (err) {
      setError(String(err));
      setTasks((ts) => ts.map((t) => (t.id === taskId ? { ...t, status: prev } : t)));
    }
  }

  if (!ready) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Kanban</h1>
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:text-brand-700">
          ← Tillbaka till projektet
        </Link>
      </div>

      {error && <Card className="text-red-600">{error}</Card>}

      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {COLUMNS.map((col) => (
            <Column
              key={col.key}
              col={col}
              tasks={tasks
                .filter((t) => t.status === col.key)
                .sort((a, b) => a.board_order - b.board_order)}
            />
          ))}
        </div>
        <DragOverlay>{active ? <TaskCard task={active} /> : null}</DragOverlay>
      </DndContext>
    </div>
  );
}
