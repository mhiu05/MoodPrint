import type { AuthError, SupabaseClient } from "@supabase/supabase-js";
import type { AuthPort } from "../ports";
import { getSupabase, isRealAuthConfigured } from "../supabase";
import { serializeAgeBand } from "./mappers";

export function authMessage(
  error: Pick<AuthError, "code" | "message"> | Error,
): string {
  const code = "code" in error ? error.code : "";
  if (code === "email_not_confirmed")
    return "Hãy xác nhận email trước khi đăng nhập. Kiểm tra cả thư mục thư rác.";
  if (
    code === "over_request_rate_limit" ||
    code === "over_email_send_rate_limit"
  )
    return "Bạn thao tác hơi nhanh. Hãy chờ một chút rồi thử lại.";
  if (code === "weak_password")
    return "Mật khẩu cần ít nhất 8 ký tự và đủ mạnh.";
  if (
    code === "invalid_credentials" ||
    code === "user_already_exists" ||
    code === "email_exists"
  )
    return "Chưa thể đăng nhập. Kiểm tra thông tin hoặc dùng chức năng quên mật khẩu.";
  if (/fetch|network/i.test(error.message))
    return "Không thể kết nối. Hãy kiểm tra mạng rồi thử lại.";
  return "Chưa thể hoàn tất xác thực. Hãy kiểm tra thông tin rồi thử lại.";
}
export function createAuthPort(
  client: () => Pick<SupabaseClient, "auth"> = getSupabase,
): AuthPort {
  const check = (error: AuthError | null) => {
    if (error) throw new Error(authMessage(error));
  };
  return {
    async getSession() {
      if (client === getSupabase && !isRealAuthConfigured()) return null;
      const { data, error } = await client().auth.getSession();
      check(error);
      return data.session ? { userId: data.session.user.id } : null;
    },
    async signIn(email, password) {
      const { error } = await client().auth.signInWithPassword({
        email,
        password,
      });
      check(error);
    },
    async signUp(input) {
      const { data, error } = await client().auth.signUp({
        email: input.email,
        password: input.password,
        options: {
          emailRedirectTo: `${location.origin}/auth`,
          data: {
            nickname: input.nickname,
            age_band: serializeAgeBand(input.ageBand),
            start_interest: input.startInterest,
          },
        },
      });
      check(error);
      return { needsEmailConfirmation: !data.session };
    },
    async signOut() {
      const { error } = await client().auth.signOut();
      check(error);
    },
    async requestPasswordReset(email) {
      const { error } = await client().auth.resetPasswordForEmail(email, {
        redirectTo: `${location.origin}/auth/reset`,
      });
      check(error);
    },
    async updatePassword(password) {
      const { error } = await client().auth.updateUser({ password });
      check(error);
    },
  };
}
