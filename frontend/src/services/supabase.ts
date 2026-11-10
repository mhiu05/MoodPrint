import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let instance: SupabaseClient | undefined;
export function isRealAuthConfigured() {
  return !!(
    import.meta.env.VITE_PUBLIC_SUPABASE_URL &&
    import.meta.env.VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  );
}
export function getSupabase(): SupabaseClient {
  if (!instance) {
    if (!isRealAuthConfigured())
      throw new Error(
        "Chưa cấu hình đăng nhập. Bạn vẫn có thể vào thử tài khoản demo.",
      );
    instance = createClient(
      import.meta.env.VITE_PUBLIC_SUPABASE_URL,
      import.meta.env.VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
      {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
          flowType: "pkce",
        },
      },
    );
  }
  return instance;
}
