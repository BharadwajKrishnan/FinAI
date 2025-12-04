import LoginForm from "@/components/LoginForm";

export default function Home() {
  return (
    <main className="min-h-screen flex">
      {/* Left side - blank for future images/icons */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-50 to-primary-100 items-center justify-center">
        <div className="text-center px-12">
          {/* Placeholder for future content */}
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center bg-white px-6 sm:px-8 md:px-12">
        <div className="w-full max-w-md">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              Welcome to FinanceApp
            </h1>
            <p className="text-gray-600">
              Sign in to manage your finances
            </p>
          </div>
          <LoginForm />
        </div>
      </div>
    </main>
  );
}

