CREATE TABLE public.policy_comparison_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    policy_a_name TEXT NOT NULL,
    policy_b_name TEXT NOT NULL,
    lob TEXT NOT NULL,
    differences_count INTEGER NOT NULL,
    recommendation TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.policy_comparison_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert their own logs" ON public.policy_comparison_logs
FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own logs" ON public.policy_comparison_logs
FOR SELECT USING (auth.uid() = user_id);
