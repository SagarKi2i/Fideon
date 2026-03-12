export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "13.0.5"
  }
  public: {
    Tables: {
      activated_models: {
        Row: {
          activated_at: string | null
          domain: Database["public"]["Enums"]["model_domain"]
          id: string
          model_id: string
          model_name: string
          user_id: string
        }
        Insert: {
          activated_at?: string | null
          domain: Database["public"]["Enums"]["model_domain"]
          id?: string
          model_id: string
          model_name: string
          user_id: string
        }
        Update: {
          activated_at?: string | null
          domain?: Database["public"]["Enums"]["model_domain"]
          id?: string
          model_id?: string
          model_name?: string
          user_id?: string
        }
        Relationships: []
      }
      agent_pipelines: {
        Row: {
          created_at: string
          description: string | null
          id: string
          is_active: boolean
          last_run_at: string | null
          name: string
          schedule_config: Json | null
          steps: Json
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          last_run_at?: string | null
          name: string
          schedule_config?: Json | null
          steps?: Json
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          last_run_at?: string | null
          name?: string
          schedule_config?: Json | null
          steps?: Json
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      agent_schedules: {
        Row: {
          created_at: string
          cron_expression: string | null
          id: string
          is_active: boolean
          last_run_at: string | null
          model_id: string
          model_name: string
          next_run_at: string | null
          prompt: string
          schedule_type: string
          scheduled_at: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          cron_expression?: string | null
          id?: string
          is_active?: boolean
          last_run_at?: string | null
          model_id: string
          model_name: string
          next_run_at?: string | null
          prompt: string
          schedule_type: string
          scheduled_at?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          cron_expression?: string | null
          id?: string
          is_active?: boolean
          last_run_at?: string | null
          model_id?: string
          model_name?: string
          next_run_at?: string | null
          prompt?: string
          schedule_type?: string
          scheduled_at?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      audit_logs: {
        Row: {
          action: string
          created_at: string
          details: Json | null
          id: string
          ip_address: string | null
          resource_id: string | null
          resource_type: string
          user_agent: string | null
          user_id: string | null
        }
        Insert: {
          action: string
          created_at?: string
          details?: Json | null
          id?: string
          ip_address?: string | null
          resource_id?: string | null
          resource_type: string
          user_agent?: string | null
          user_id?: string | null
        }
        Update: {
          action?: string
          created_at?: string
          details?: Json | null
          id?: string
          ip_address?: string | null
          resource_id?: string | null
          resource_type?: string
          user_agent?: string | null
          user_id?: string | null
        }
        Relationships: []
      }
      app_users: {
        Row: {
          created_at: string
          email: string
          full_name: string | null
          last_login_at: string | null
          metadata: Json
          status: string
          tenant_id: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          email: string
          full_name?: string | null
          last_login_at?: string | null
          metadata?: Json
          status?: string
          tenant_id?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          email?: string
          full_name?: string | null
          last_login_at?: string | null
          metadata?: Json
          status?: string
          tenant_id?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "app_users_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      chat_conversations: {
        Row: {
          created_at: string | null
          id: string
          model_id: string | null
          title: string | null
          updated_at: string | null
          user_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          model_id?: string | null
          title?: string | null
          updated_at?: string | null
          user_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          model_id?: string | null
          title?: string | null
          updated_at?: string | null
          user_id?: string
        }
        Relationships: []
      }
      chat_messages: {
        Row: {
          content: string
          conversation_id: string
          created_at: string | null
          id: string
          role: string
        }
        Insert: {
          content: string
          conversation_id: string
          created_at?: string | null
          id?: string
          role: string
        }
        Update: {
          content?: string
          conversation_id?: string
          created_at?: string | null
          id?: string
          role?: string
        }
        Relationships: [
          {
            foreignKeyName: "chat_messages_conversation_id_fkey"
            columns: ["conversation_id"]
            isOneToOne: false
            referencedRelation: "chat_conversations"
            referencedColumns: ["id"]
          },
        ]
      }
      decision_reviews: {
        Row: {
          ai_recommendation: string | null
          confidence_score: number | null
          created_at: string
          decision_type: string
          domain: string
          id: string
          input_data: Json | null
          output_data: Json | null
          pod_model_id: string
          pod_model_name: string
          reviewed_at: string | null
          reviewer_id: string | null
          reviewer_notes: string | null
          status: string
          summary: string | null
          threshold_exceeded: boolean | null
          title: string
          updated_at: string
          user_id: string
        }
        Insert: {
          ai_recommendation?: string | null
          confidence_score?: number | null
          created_at?: string
          decision_type: string
          domain: string
          id?: string
          input_data?: Json | null
          output_data?: Json | null
          pod_model_id: string
          pod_model_name: string
          reviewed_at?: string | null
          reviewer_id?: string | null
          reviewer_notes?: string | null
          status?: string
          summary?: string | null
          threshold_exceeded?: boolean | null
          title: string
          updated_at?: string
          user_id: string
        }
        Update: {
          ai_recommendation?: string | null
          confidence_score?: number | null
          created_at?: string
          decision_type?: string
          domain?: string
          id?: string
          input_data?: Json | null
          output_data?: Json | null
          pod_model_id?: string
          pod_model_name?: string
          reviewed_at?: string | null
          reviewer_id?: string | null
          reviewer_notes?: string | null
          status?: string
          summary?: string | null
          threshold_exceeded?: boolean | null
          title?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      device_analytics: {
        Row: {
          cpu_load_avg: number | null
          created_at: string
          date: string
          device_id: string
          error_count: number
          gpu_load_avg: number | null
          id: string
          model_id: string
          query_count: number
          token_usage: number
        }
        Insert: {
          cpu_load_avg?: number | null
          created_at?: string
          date?: string
          device_id: string
          error_count?: number
          gpu_load_avg?: number | null
          id?: string
          model_id: string
          query_count?: number
          token_usage?: number
        }
        Update: {
          cpu_load_avg?: number | null
          created_at?: string
          date?: string
          device_id?: string
          error_count?: number
          gpu_load_avg?: number | null
          id?: string
          model_id?: string
          query_count?: number
          token_usage?: number
        }
        Relationships: [
          {
            foreignKeyName: "device_analytics_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      device_licenses: {
        Row: {
          created_at: string
          device_id: string
          expires_at: string | null
          id: string
          issued_at: string
          issued_by: string | null
          license_type: Database["public"]["Enums"]["license_type"]
          notes: string | null
          status: Database["public"]["Enums"]["license_status"]
          suspended_at: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          device_id: string
          expires_at?: string | null
          id?: string
          issued_at?: string
          issued_by?: string | null
          license_type?: Database["public"]["Enums"]["license_type"]
          notes?: string | null
          status?: Database["public"]["Enums"]["license_status"]
          suspended_at?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          device_id?: string
          expires_at?: string | null
          id?: string
          issued_at?: string
          issued_by?: string | null
          license_type?: Database["public"]["Enums"]["license_type"]
          notes?: string | null
          status?: Database["public"]["Enums"]["license_status"]
          suspended_at?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "device_licenses_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      device_models: {
        Row: {
          allocated_at: string
          allocated_by: string | null
          device_id: string
          domain: string
          id: string
          is_downloaded: boolean | null
          last_synced_at: string | null
          model_id: string
          model_name: string
          ollama_model_name: string | null
        }
        Insert: {
          allocated_at?: string
          allocated_by?: string | null
          device_id: string
          domain: string
          id?: string
          is_downloaded?: boolean | null
          last_synced_at?: string | null
          model_id: string
          model_name: string
          ollama_model_name?: string | null
        }
        Update: {
          allocated_at?: string
          allocated_by?: string | null
          device_id?: string
          domain?: string
          id?: string
          is_downloaded?: boolean | null
          last_synced_at?: string | null
          model_id?: string
          model_name?: string
          ollama_model_name?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "device_models_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      device_sync_logs: {
        Row: {
          created_at: string
          details: Json | null
          device_id: string
          id: string
          status: string
          sync_type: string
        }
        Insert: {
          created_at?: string
          details?: Json | null
          device_id: string
          id?: string
          status: string
          sync_type: string
        }
        Update: {
          created_at?: string
          details?: Json | null
          device_id?: string
          id?: string
          status?: string
          sync_type?: string
        }
        Relationships: [
          {
            foreignKeyName: "device_sync_logs_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      device_usage_logs: {
        Row: {
          device_id: string
          duration_seconds: number | null
          id: string
          logged_at: string
          model_id: string
          prompt_count: number | null
          tokens_used: number | null
        }
        Insert: {
          device_id: string
          duration_seconds?: number | null
          id?: string
          logged_at?: string
          model_id: string
          prompt_count?: number | null
          tokens_used?: number | null
        }
        Update: {
          device_id?: string
          duration_seconds?: number | null
          id?: string
          logged_at?: string
          model_id?: string
          prompt_count?: number | null
          tokens_used?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "device_usage_logs_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      devices: {
        Row: {
          app_version: string | null
          created_at: string
          device_name: string
          device_token: string
          id: string
          is_active: boolean
          last_seen_at: string | null
          metadata: Json | null
          os_type: string | null
          registered_at: string
          registered_by: string | null
          status: string
          updated_at: string
        }
        Insert: {
          app_version?: string | null
          created_at?: string
          device_name: string
          device_token: string
          id?: string
          is_active?: boolean
          last_seen_at?: string | null
          metadata?: Json | null
          os_type?: string | null
          registered_at?: string
          registered_by?: string | null
          status?: string
          updated_at?: string
        }
        Update: {
          app_version?: string | null
          created_at?: string
          device_name?: string
          device_token?: string
          id?: string
          is_active?: boolean
          last_seen_at?: string | null
          metadata?: Json | null
          os_type?: string | null
          registered_at?: string
          registered_by?: string | null
          status?: string
          updated_at?: string
        }
        Relationships: []
      }
      documents: {
        Row: {
          file_size: number
          file_type: string
          filename: string
          id: string
          storage_path: string
          uploaded_at: string | null
          user_id: string
        }
        Insert: {
          file_size: number
          file_type: string
          filename: string
          id?: string
          storage_path: string
          uploaded_at?: string | null
          user_id: string
        }
        Update: {
          file_size?: number
          file_type?: string
          filename?: string
          id?: string
          storage_path?: string
          uploaded_at?: string | null
          user_id?: string
        }
        Relationships: []
      }
      federated_rounds: {
        Row: {
          aggregated_model_path: string | null
          aggregation_method: string | null
          completed_at: string | null
          current_participants: number | null
          distributed_at: string | null
          id: string
          metrics: Json | null
          min_participants: number | null
          model_id: string
          round_number: number
          started_at: string
          status: string
        }
        Insert: {
          aggregated_model_path?: string | null
          aggregation_method?: string | null
          completed_at?: string | null
          current_participants?: number | null
          distributed_at?: string | null
          id?: string
          metrics?: Json | null
          min_participants?: number | null
          model_id: string
          round_number: number
          started_at?: string
          status?: string
        }
        Update: {
          aggregated_model_path?: string | null
          aggregation_method?: string | null
          completed_at?: string | null
          current_participants?: number | null
          distributed_at?: string | null
          id?: string
          metrics?: Json | null
          min_participants?: number | null
          model_id?: string
          round_number?: number
          started_at?: string
          status?: string
        }
        Relationships: []
      }
      federated_updates: {
        Row: {
          device_id: string
          gradient_hash: string
          gradient_size_bytes: number | null
          id: string
          metrics: Json | null
          model_id: string
          privacy_noise_added: boolean | null
          round_number: number
          status: string
          storage_path: string | null
          submitted_at: string
        }
        Insert: {
          device_id: string
          gradient_hash: string
          gradient_size_bytes?: number | null
          id?: string
          metrics?: Json | null
          model_id: string
          privacy_noise_added?: boolean | null
          round_number?: number
          status?: string
          storage_path?: string | null
          submitted_at?: string
        }
        Update: {
          device_id?: string
          gradient_hash?: string
          gradient_size_bytes?: number | null
          id?: string
          metrics?: Json | null
          model_id?: string
          privacy_noise_added?: boolean | null
          round_number?: number
          status?: string
          storage_path?: string | null
          submitted_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "federated_updates_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      model_endpoints: {
        Row: {
          created_at: string | null
          endpoint_url: string
          id: string
          max_tokens: number | null
          name: string
          provider: Database["public"]["Enums"]["model_provider"]
          system_prompt: string | null
          temperature: number | null
          updated_at: string | null
          user_id: string
        }
        Insert: {
          created_at?: string | null
          endpoint_url: string
          id?: string
          max_tokens?: number | null
          name: string
          provider: Database["public"]["Enums"]["model_provider"]
          system_prompt?: string | null
          temperature?: number | null
          updated_at?: string | null
          user_id: string
        }
        Update: {
          created_at?: string | null
          endpoint_url?: string
          id?: string
          max_tokens?: number | null
          name?: string
          provider?: Database["public"]["Enums"]["model_provider"]
          system_prompt?: string | null
          temperature?: number | null
          updated_at?: string | null
          user_id?: string
        }
        Relationships: []
      }
      model_catalog: {
        Row: {
          created_at: string
          description: string | null
          domain: string
          id: string
          is_active: boolean
          metadata: Json
          model_id: string
          model_name: string
          provider: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          domain: string
          id?: string
          is_active?: boolean
          metadata?: Json
          model_id: string
          model_name: string
          provider: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          description?: string | null
          domain?: string
          id?: string
          is_active?: boolean
          metadata?: Json
          model_id?: string
          model_name?: string
          provider?: string
          updated_at?: string
        }
        Relationships: []
      }
      model_packs: {
        Row: {
          created_at: string
          created_by: string | null
          description: string | null
          domain: string
          id: string
          models: Json
          name: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          created_by?: string | null
          description?: string | null
          domain: string
          id?: string
          models?: Json
          name: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          created_by?: string | null
          description?: string | null
          domain?: string
          id?: string
          models?: Json
          name?: string
          updated_at?: string
        }
        Relationships: []
      }
      pod_activation_requests: {
        Row: {
          domain: string
          id: string
          model_id: string
          model_name: string
          rejection_reason: string | null
          requested_at: string
          reviewed_at: string | null
          reviewed_by: string | null
          status: string
          user_id: string
        }
        Insert: {
          domain: string
          id?: string
          model_id: string
          model_name: string
          rejection_reason?: string | null
          requested_at?: string
          reviewed_at?: string | null
          reviewed_by?: string | null
          status?: string
          user_id: string
        }
        Update: {
          domain?: string
          id?: string
          model_id?: string
          model_name?: string
          rejection_reason?: string | null
          requested_at?: string
          reviewed_at?: string | null
          reviewed_by?: string | null
          status?: string
          user_id?: string
        }
        Relationships: []
      }
      policy_comparisons: {
        Row: {
          comparison_result: Json | null
          created_at: string | null
          id: string
          policy_a_document_id: string | null
          policy_b_document_id: string | null
          user_id: string
        }
        Insert: {
          comparison_result?: Json | null
          created_at?: string | null
          id?: string
          policy_a_document_id?: string | null
          policy_b_document_id?: string | null
          user_id: string
        }
        Update: {
          comparison_result?: Json | null
          created_at?: string | null
          id?: string
          policy_a_document_id?: string | null
          policy_b_document_id?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "policy_comparisons_policy_a_document_id_fkey"
            columns: ["policy_a_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "policy_comparisons_policy_b_document_id_fkey"
            columns: ["policy_b_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
        ]
      }
      roles: {
        Row: {
          created_at: string
          description: string | null
          display_name: string
          permissions: Json
          role: Database["public"]["Enums"]["app_role"]
          updated_at: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          display_name: string
          permissions?: Json
          role: Database["public"]["Enums"]["app_role"]
          updated_at?: string
        }
        Update: {
          created_at?: string
          description?: string | null
          display_name?: string
          permissions?: Json
          role?: Database["public"]["Enums"]["app_role"]
          updated_at?: string
        }
        Relationships: []
      }
      tenants: {
        Row: {
          created_at: string
          id: string
          is_active: boolean
          metadata: Json
          name: string
          slug: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: string
          is_active?: boolean
          metadata?: Json
          name: string
          slug: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: string
          is_active?: boolean
          metadata?: Json
          name?: string
          slug?: string
          updated_at?: string
        }
        Relationships: []
      }
      training_feedback: {
        Row: {
          corrected_response: string | null
          created_at: string
          device_id: string
          feedback_type: string
          id: string
          is_used_for_training: boolean | null
          metadata: Json | null
          model_id: string
          original_response: string
          prompt: string
          rating: number | null
        }
        Insert: {
          corrected_response?: string | null
          created_at?: string
          device_id: string
          feedback_type?: string
          id?: string
          is_used_for_training?: boolean | null
          metadata?: Json | null
          model_id: string
          original_response: string
          prompt: string
          rating?: number | null
        }
        Update: {
          corrected_response?: string | null
          created_at?: string
          device_id?: string
          feedback_type?: string
          id?: string
          is_used_for_training?: boolean | null
          metadata?: Json | null
          model_id?: string
          original_response?: string
          prompt?: string
          rating?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "training_feedback_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      training_jobs: {
        Row: {
          completed_at: string | null
          config: Json | null
          created_at: string
          device_id: string
          error_message: string | null
          feedback_count: number | null
          id: string
          metrics: Json | null
          model_id: string
          started_at: string | null
          status: string
          training_type: string
          updated_at: string
        }
        Insert: {
          completed_at?: string | null
          config?: Json | null
          created_at?: string
          device_id: string
          error_message?: string | null
          feedback_count?: number | null
          id?: string
          metrics?: Json | null
          model_id: string
          started_at?: string | null
          status?: string
          training_type?: string
          updated_at?: string
        }
        Update: {
          completed_at?: string | null
          config?: Json | null
          created_at?: string
          device_id?: string
          error_message?: string | null
          feedback_count?: number | null
          id?: string
          metrics?: Json | null
          model_id?: string
          started_at?: string | null
          status?: string
          training_type?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "training_jobs_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      user_roles: {
        Row: {
          created_at: string | null
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
      visual_workflows: {
        Row: {
          created_at: string
          description: string | null
          edges: Json
          id: string
          is_active: boolean
          last_run_at: string | null
          name: string
          nodes: Json
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          edges?: Json
          id?: string
          is_active?: boolean
          last_run_at?: string | null
          name: string
          nodes?: Json
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          description?: string | null
          edges?: Json
          id?: string
          is_active?: boolean
          last_run_at?: string | null
          name?: string
          nodes?: Json
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      workflow_runs: {
        Row: {
          completed_at: string | null
          current_step: number | null
          id: string
          started_at: string
          status: string
          step_results: Json | null
          user_id: string
          workflow_id: string
        }
        Insert: {
          completed_at?: string | null
          current_step?: number | null
          id?: string
          started_at?: string
          status?: string
          step_results?: Json | null
          user_id: string
          workflow_id: string
        }
        Update: {
          completed_at?: string | null
          current_step?: number | null
          id?: string
          started_at?: string
          status?: string
          step_results?: Json | null
          user_id?: string
          workflow_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "workflow_runs_workflow_id_fkey"
            columns: ["workflow_id"]
            isOneToOne: false
            referencedRelation: "workflows"
            referencedColumns: ["id"]
          },
        ]
      }
      workflows: {
        Row: {
          category: string | null
          created_at: string
          description: string | null
          id: string
          is_template: boolean | null
          parsed_steps: Json | null
          sop_text: string
          title: string
          updated_at: string
          user_id: string
        }
        Insert: {
          category?: string | null
          created_at?: string
          description?: string | null
          id?: string
          is_template?: boolean | null
          parsed_steps?: Json | null
          sop_text: string
          title: string
          updated_at?: string
          user_id: string
        }
        Update: {
          category?: string | null
          created_at?: string
          description?: string | null
          id?: string
          is_template?: boolean | null
          parsed_steps?: Json | null
          sop_text?: string
          title?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      generate_device_token: { Args: never; Returns: string }
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "global_admin" | "admin" | "user" | "viewer" | "guest"
      license_status: "active" | "suspended" | "expired"
      license_type: "standard" | "premium" | "model_based"
      model_domain: "insurance" | "healthcare" | "banking" | "legal" | "travel"
      model_provider: "ollama" | "lmstudio" | "openai" | "custom"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["global_admin", "admin", "user", "viewer", "guest"],
      license_status: ["active", "suspended", "expired"],
      license_type: ["standard", "premium", "model_based"],
      model_domain: ["insurance", "healthcare", "banking", "legal", "travel"],
      model_provider: ["ollama", "lmstudio", "openai", "custom"],
    },
  },
} as const
