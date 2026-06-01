// Speglar API-DTO:erna i apps/api/app/dto.py.

export type ProjectStatus = "draft" | "generating" | "ready" | "failed";
export type TaskStatus = "backlog" | "todo" | "in_progress" | "review" | "done";

export interface Project {
  id: string;
  name: string;
  description: string;
  target_audience: string | null;
  business_goals: string | null;
  budget: string | null;
  timeframe: string | null;
  status: ProjectStatus;
  created_at: string;
}

export interface Task {
  id: string;
  story_id: string;
  sprint_id: string | null;
  title: string;
  description: string | null;
  type: string;
  status: TaskStatus;
  estimate: number | null;
  board_order: number;
}

export interface Story {
  id: string;
  role: string;
  want: string;
  so_that: string;
  acceptance_criteria: string[];
  order: number;
  tasks: Task[];
}

export interface Epic {
  id: string;
  roadmap_id: string | null;
  title: string;
  description: string | null;
  priority: string;
  business_value: string | null;
  order: number;
  stories: Story[];
}

export interface RoadmapPhase {
  id: string;
  phase: number;
  title: string;
  summary: string | null;
  order: number;
}

export interface Sprint {
  id: string;
  name: string;
  goal: string | null;
  capacity_points: number | null;
  start_date: string | null;
  end_date: string | null;
  order: number;
}

export interface Architecture {
  stack: { layer: string; technology: string; rationale: string }[];
  data_model: { name: string; fields: string[]; relations: string[] }[];
  api_design: { method: string; path: string; purpose: string }[];
  rationale: string | null;
}

export interface Risk {
  id: string;
  title: string;
  description: string | null;
  severity: string;
  affected_epics: string[];
  recommendation: string | null;
}

export interface ProjectDetail extends Project {
  roadmaps: RoadmapPhase[];
  epics: Epic[];
  sprints: Sprint[];
  risks: Risk[];
  architecture: Architecture | null;
}

export interface GenerateRequest {
  team_size: number;
  sprint_length_weeks: number;
  velocity_per_dev: number;
}

export interface BoardColumn {
  status: TaskStatus;
  tasks: Task[];
}

export interface Board {
  columns: BoardColumn[];
}

// SSE-payload från worker via Redis pub/sub.
export interface AgentStatus {
  agent: string;
  status: "running" | "done" | "failed";
  progress: number | null;
  error?: string;
}
