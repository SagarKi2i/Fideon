-- Add unique constraint to user_roles to prevent duplicate roles per user
ALTER TABLE user_roles ADD CONSTRAINT user_roles_user_id_unique UNIQUE (user_id);