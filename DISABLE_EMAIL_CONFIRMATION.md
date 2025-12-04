# How to Disable Email Confirmation in Supabase

If you want users to be able to sign in immediately after signup (without email confirmation), you need to disable email confirmation in your Supabase project settings.

## Steps to Disable Email Confirmation

1. **Go to your Supabase Dashboard**
   - Visit: https://supabase.com/dashboard
   - Select your project: `fuvloymbqvdmxasxajif`

2. **Navigate to Authentication Settings**
   - Click on **Authentication** in the left sidebar
   - Click on **Settings** (or go to Authentication → Settings)

3. **Disable Email Confirmation**
   - Scroll down to **Email Auth** section
   - Find **"Enable email confirmations"** toggle
   - **Turn it OFF** (disable it)

4. **Save Changes**
   - The changes are saved automatically

## After Disabling Email Confirmation

- Users can sign in immediately after signup
- No email confirmation required
- Tokens will be returned immediately upon signup

## Important Notes

⚠️ **Security Consideration**: Disabling email confirmation means anyone with an email address can create an account. This is fine for development but consider enabling it for production.

✅ **For Development**: It's recommended to disable email confirmation for easier testing.

## Alternative: Keep Email Confirmation Enabled

If you want to keep email confirmation enabled:
- Users will receive a confirmation email after signup
- They must click the confirmation link before they can sign in
- The signup will succeed but they'll need to confirm their email first

The backend code has been updated to handle both cases gracefully.

