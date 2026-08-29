/**
 * API Client for Meeting Intelligence System
 * Handles all backend API calls with authentication
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Get the auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

/**
 * Handle 401/404 auth errors by clearing the stale token and redirecting to login.
 */
function handleAuthFailure(status: number) {
  if (status === 401 || status === 403 || status === 404) {
    if (typeof window !== "undefined" && localStorage.getItem("auth_token")) {
      localStorage.removeItem("auth_token");
      // Only redirect if we're not already on an auth page
      const path = window.location.pathname;
      if (!path.startsWith("/login") && !path.startsWith("/signup")) {
        window.location.href = "/login";
      }
    }
  }
}

/**
 * Generic fetch wrapper with auth headers
 */
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    handleAuthFailure(response.status);
    const errorText = await response.text();
    throw new Error(
      `API Error ${response.status}: ${errorText || response.statusText}`
    );
  }

  return response.json();
}

/**
 * Generic fetch wrapper for service-to-service calls (STT pipeline)
 */
async function serviceCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "x-service-key": "change-me-in-env",
    ...((options.headers as Record<string, string>) || {}),
  };

  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    handleAuthFailure(response.status);
    const errorText = await response.text();
    throw new Error(
      `Service API Error ${response.status}: ${errorText || response.statusText}`
    );
  }

  return response.json();
}

// ============================================================================
// Authentication
// ============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  name: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

/**
 * Login user
 */
export async function login(data: LoginRequest): Promise<AuthResponse> {
  const formData = new URLSearchParams();
  formData.append("username", data.email);
  formData.append("password", data.password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Login failed: ${errorText || response.statusText}`);
  }

  const result: AuthResponse = await response.json();

  // Store token in localStorage
  if (typeof window !== "undefined") {
    localStorage.setItem("auth_token", result.access_token);
  }

  return result;
}

/**
 * Signup new user
 */
export async function signup(data: SignupRequest): Promise<AuthResponse> {
  // Step 1: Register the user
  const registerResponse = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      full_name: data.name,
      email: data.email,
      password: data.password,
    }),
  });

  if (!registerResponse.ok) {
    const errorText = await registerResponse.text();
    throw new Error(`Signup failed: ${errorText || registerResponse.statusText}`);
  }

  // Step 2: Login to get token
  const loginResponse = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      username: data.email,
      password: data.password,
    }).toString(),
  });

  if (!loginResponse.ok) {
    throw new Error("Registration successful but login failed. Please try logging in.");
  }

  const result: AuthResponse = await loginResponse.json();

  // Store token in localStorage
  if (typeof window !== "undefined") {
    localStorage.setItem("auth_token", result.access_token);
  }

  return result;
}

/**
 * Logout user
 */
export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("auth_token");
  }
}

/**
 * Get current user info
 */
export async function getCurrentUser(): Promise<any> {
  return apiCall("/users/me");
}

// ============================================================================
// Meetings
// ============================================================================

export interface CreateMeetingRequest {
  title: string;
  description?: string;
  meeting_date?: string;
  participants?: Array<{ name: string; email?: string }>;
}

export interface Meeting {
  id: string;
  title: string;
  description?: string;
  status: string;
  duration_seconds?: number;
  meeting_date?: string;
  created_at: string;
  updated_at: string;
  files: any[];
  participants: any[];
}

export interface PaginatedMeetings {
  total: number;
  page: number;
  page_size: number;
  items: Array<{
    id: string;
    title: string;
    status: string;
    duration_seconds?: number;
    meeting_date?: string;
    created_at: string;
    file_count: number;
  }>;
}

/**
 * Create a new meeting
 */
export async function createMeeting(data: CreateMeetingRequest): Promise<Meeting> {
  return apiCall<Meeting>("/meetings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * List user's meetings
 */
export async function listMeetings(
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedMeetings> {
  return apiCall<PaginatedMeetings>(
    `/meetings?page=${page}&page_size=${pageSize}`
  );
}

/**
 * Get meeting by ID
 */
export async function getMeeting(meetingId: string): Promise<Meeting> {
  return apiCall<Meeting>(`/meetings/${meetingId}`);
}

/**
 * Update meeting
 */
export async function updateMeeting(
  meetingId: string,
  data: Partial<CreateMeetingRequest>
): Promise<Meeting> {
  return apiCall<Meeting>(`/meetings/${meetingId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Delete meeting
 */
export async function deleteMeeting(meetingId: string): Promise<void> {
  return apiCall<void>(`/meetings/${meetingId}`, {
    method: "DELETE",
  });
}

// ============================================================================
// File Upload
// ============================================================================

/**
 * Upload audio/video file to meeting
 */
export async function uploadFile(
  meetingId: string,
  file: File
): Promise<any> {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append("upload_file", file);

  const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/files`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Upload failed: ${errorText || response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// STT (Speech-to-Text)
// ============================================================================

export interface TranscriptSegment {
  start_time: number;
  end_time: number;
  speaker: string;
  text: string;
  confidence: number;
  speaker_id?: string;
}

export interface STTProcessingResponse {
  meeting_id: string;
  status: string;
  raw_text: string;
  formatted_text: string;
  segments: TranscriptSegment[];
  speaker_mappings: Array<{
    diarizer_speaker: string;
    participant_id: string | null;
  }>;
  processing_time_seconds: number;
  transcriber_model: string;
}

export interface TranscriptResponse {
  meeting_id: string;
  raw_text: string;
  formatted_text: string;
  language: string;
  segments: TranscriptSegment[];
  overall_confidence?: number;
  duration_seconds?: number;
  transcriber_model: string;
}

/**
 * Trigger STT processing for a meeting
 */
export async function processSTT(meetingId: string): Promise<STTProcessingResponse> {
  return serviceCall<STTProcessingResponse>(
    `/stt/meetings/${meetingId}/process-stt`,
    {
      method: "POST",
    }
  );
}

/**
 * Get transcript for a meeting
 */
export async function getTranscript(meetingId: string): Promise<TranscriptResponse> {
  return serviceCall<TranscriptResponse>(
    `/stt/meetings/${meetingId}/transcript`
  );
}

/**
 * Update speaker-to-participant mapping
 */
export async function updateSpeakerMapping(
  meetingId: string,
  mappings: Array<{ participant_id: string; speaker_label: string }>
): Promise<any> {
  return serviceCall(`/stt/meetings/${meetingId}/speaker-mapping`, {
    method: "POST",
    body: JSON.stringify({ mappings }),
  });
}
