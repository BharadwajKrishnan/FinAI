import LoginForm from "@/components/LoginForm";

export default function Home() {
  return (
    <main className="min-h-screen flex">
      {/* Left side - Features */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-50 to-primary-100 items-center justify-center">
        <div className="text-left px-12 max-w-md">
          <h2 className="text-3xl font-bold text-gray-900 mb-6">
            Highlight of Features
          </h2>
          <ul className="space-y-4">
            <li className="flex items-start">
              <svg
                className="w-6 h-6 text-primary-600 mr-3 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-gray-700 text-lg">
                <strong>PulseCheck:</strong> AI Market & Portfolio Snapshots
              </span>
            </li>
            <li className="flex items-start">
              <svg
                className="w-6 h-6 text-primary-600 mr-3 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-gray-700 text-lg">
                <strong>WisdomTap:</strong> Explain complex finance topics in simple words
              </span>
            </li>
            <li className="flex items-start">
              <svg
                className="w-6 h-6 text-primary-600 mr-3 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-gray-700 text-lg">
                <strong>ChatYourData:</strong> Ask anything about your portfolio and expenses
              </span>
            </li>
            <li className="flex items-start">
              <svg
                className="w-6 h-6 text-primary-600 mr-3 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-gray-700 text-lg">
                <strong>VaultWatchman:</strong> AI spending auditor tracks your expenses against your portfolio health, flags unwise spending patterns, suggests smart cuts
              </span>
            </li>
            <li className="flex items-start">
              <svg
                className="w-6 h-6 text-primary-600 mr-3 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-gray-700 text-lg">
                <strong>ShieldScan:</strong> Detect portfolio risks & imbalances
              </span>
            </li>
            <li className="flex items-start">
              <svg
                className="w-6 h-6 text-primary-600 mr-3 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-gray-700 text-lg">
                <strong>SnapLog:</strong> Snap receipt → add expense instantly
              </span>
            </li>
          </ul>
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

