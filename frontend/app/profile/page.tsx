"use client";

import { useState, useEffect } from "react";

type FamilyMemberRelationship = "Self" | "Son" | "Daughter" | "Spouse" | "Father" | "Mother" | "Grandfather" | "Grandmother" | "Brother" | "Sister";

export default function ProfilePage() {
  const [familyMembers, setFamilyMembers] = useState<Array<{
    id: string;
    name: string;
    relationship: string;
    notes?: string;
  }>>([]);
  const [isFamilyMemberModalOpen, setIsFamilyMemberModalOpen] = useState(false);
  const [editingFamilyMemberId, setEditingFamilyMemberId] = useState<string | null>(null);
  const [familyMemberName, setFamilyMemberName] = useState("");
  const [familyMemberRelationship, setFamilyMemberRelationship] = useState<FamilyMemberRelationship>("Son");
  const [familyMemberNotes, setFamilyMemberNotes] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Fetch family members from database
  const fetchFamilyMembers = async () => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        window.location.href = "/";
        return;
      }

      // Try with trailing slash first (to avoid redirect)
      let response = await fetch("/api/family-members/", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        redirect: "follow", // Follow redirects
      });

      // If 404 or other error, try without trailing slash
      if (!response.ok && response.status !== 200) {
        response = await fetch("/api/family-members", {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
          redirect: "follow",
        });
      }

      if (response.ok) {
        const members = await response.json();
        setFamilyMembers(members || []);
      } else if (response.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/";
      } else {
        console.error(`Failed to fetch family members: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error("Error fetching family members:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFamilyMembers();
  }, []);

  if (isLoading) {
    return (
      <main className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading profile...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
            <p className="text-sm text-gray-600">Manage your family members</p>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => (window.location.href = "/assets")}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
            >
              Financial Assets
            </button>
            <button
              onClick={() => (window.location.href = "/expenses")}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
            >
              Expense Tracker
            </button>
            <button
              onClick={() => {
                localStorage.removeItem("access_token");
                localStorage.removeItem("refresh_token");
                window.location.href = "/";
              }}
              className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          {/* Family Members Section */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Family Members</h2>
                <p className="text-sm text-gray-600 mt-1">Add and manage family members to track their net worth separately</p>
              </div>
              <button
                onClick={() => {
                  setEditingFamilyMemberId(null);
                  setFamilyMemberName("");
                  setFamilyMemberRelationship("Son");
                  setFamilyMemberNotes("");
                  setIsFamilyMemberModalOpen(true);
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
              >
                + Add Family Member
              </button>
            </div>
            
            {familyMembers.length === 0 ? (
              <div className="text-center py-12">
                <svg
                  className="mx-auto h-16 w-16 text-gray-400 mb-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                  />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Family Members Added</h3>
                <p className="text-gray-500 mb-4">Add family members to track their net worth separately</p>
                <button
                  onClick={() => {
                    setEditingFamilyMemberId(null);
                    setFamilyMemberName("");
                    setFamilyMemberRelationship("Son");
                    setFamilyMemberNotes("");
                    setIsFamilyMemberModalOpen(true);
                  }}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                >
                  Add Your First Family Member
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {familyMembers.map((member) => (
                  <div
                    key={member.id}
                    className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h4 className="text-base font-semibold text-gray-900">{member.name}</h4>
                        <p className="text-sm text-gray-600">{member.relationship}</p>
                        {member.notes && (
                          <p className="text-xs text-gray-500 mt-2">{member.notes}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setEditingFamilyMemberId(member.id);
                            setFamilyMemberName(member.name);
                            setFamilyMemberRelationship(member.relationship as FamilyMemberRelationship);
                            setFamilyMemberNotes(member.notes || "");
                            setIsFamilyMemberModalOpen(true);
                          }}
                          className="p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                          title="Edit family member"
                        >
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                            />
                          </svg>
                        </button>
                        <button
                          onClick={async () => {
                            if (window.confirm(`Are you sure you want to delete ${member.name}? This will unassign all their assets.`)) {
                              const accessToken = localStorage.getItem("access_token");
                              if (!accessToken) return;
                              
                              const response = await fetch(`/api/family-members/${member.id}`, {
                                method: "DELETE",
                                headers: {
                                  Authorization: `Bearer ${accessToken}`,
                                },
                              });
                              
                              if (response.ok) {
                                setFamilyMembers(prev => prev.filter(m => m.id !== member.id));
                                // Refresh assets page if it's open
                                if (window.location.pathname === "/assets") {
                                  window.location.reload();
                                }
                              } else {
                                alert("Failed to delete family member. Please try again.");
                              }
                            }
                          }}
                          className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                          title="Delete family member"
                        >
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Family Member Modal */}
      {isFamilyMemberModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
            onClick={() => setIsFamilyMemberModalOpen(false)}
          ></div>

          {/* Modal */}
          <div className="flex min-h-full items-center justify-center p-4">
            <div
              className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {editingFamilyMemberId ? "Edit Family Member" : "Add Family Member"}
                </h2>
                <button
                  onClick={() => setIsFamilyMemberModalOpen(false)}
                  className="text-gray-400 hover:text-gray-500 focus:outline-none"
                >
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              {/* Form */}
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  
                  const accessToken = localStorage.getItem("access_token");
                  if (!accessToken) return;

                  const familyMemberData = {
                    name: familyMemberName,
                    relationship: familyMemberRelationship,
                    notes: familyMemberNotes || undefined,
                  };

                  try {
                    if (editingFamilyMemberId) {
                      // Update existing family member
                      const response = await fetch(`/api/family-members/${editingFamilyMemberId}`, {
                        method: "PUT",
                        headers: {
                          "Content-Type": "application/json",
                          Authorization: `Bearer ${accessToken}`,
                        },
                        body: JSON.stringify(familyMemberData),
                      });

                      if (!response.ok) {
                        const error = await response.json().catch(() => ({ detail: "Failed to update family member" }));
                        throw new Error(error.detail || "Failed to update family member");
                      }

                      const updated = await response.json();
                      setFamilyMembers(prev => prev.map(m => m.id === editingFamilyMemberId ? updated : m));
                    } else {
                      // Create new family member
                      const response = await fetch("/api/family-members", {
                        method: "POST",
                        headers: {
                          "Content-Type": "application/json",
                          Authorization: `Bearer ${accessToken}`,
                        },
                        body: JSON.stringify(familyMemberData),
                      });

                      if (!response.ok) {
                        const error = await response.json().catch(() => ({ detail: "Failed to create family member" }));
                        throw new Error(error.detail || "Failed to create family member");
                      }

                      const created = await response.json();
                      setFamilyMembers(prev => [...prev, created]);
                    }

                    // Reset form
                    setEditingFamilyMemberId(null);
                    setFamilyMemberName("");
                    setFamilyMemberRelationship("Son");
                    setFamilyMemberNotes("");
                    setIsFamilyMemberModalOpen(false);
                  } catch (error) {
                    console.error("Error saving family member:", error);
                    alert(error instanceof Error ? error.message : "Failed to save family member. Please try again.");
                  }
                }}
                className="space-y-4"
              >
                <div>
                  <label
                    htmlFor="family-member-name"
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    id="family-member-name"
                    value={familyMemberName}
                    onChange={(e) => setFamilyMemberName(e.target.value)}
                    required
                    placeholder="Enter family member name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                  />
                </div>

                <div>
                  <label
                    htmlFor="family-member-relationship"
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Relationship <span className="text-red-500">*</span>
                  </label>
                  <select
                    id="family-member-relationship"
                    value={familyMemberRelationship}
                    onChange={(e) => setFamilyMemberRelationship(e.target.value as FamilyMemberRelationship)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                  >
                    <option value="Self">Self</option>
                    <option value="Son">Son</option>
                    <option value="Daughter">Daughter</option>
                    <option value="Spouse">Spouse</option>
                    <option value="Father">Father</option>
                    <option value="Mother">Mother</option>
                    <option value="Grandfather">Grandfather</option>
                    <option value="Grandmother">Grandmother</option>
                    <option value="Brother">Brother</option>
                    <option value="Sister">Sister</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="family-member-notes"
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Notes <span className="text-gray-400 text-xs">(Optional)</span>
                  </label>
                  <textarea
                    id="family-member-notes"
                    value={familyMemberNotes}
                    onChange={(e) => setFamilyMemberNotes(e.target.value)}
                    rows={3}
                    placeholder="Additional notes about this family member"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                  />
                </div>

                {/* Form Actions */}
                <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
                  <button
                    type="button"
                    onClick={() => {
                      setIsFamilyMemberModalOpen(false);
                      setEditingFamilyMemberId(null);
                      setFamilyMemberName("");
                      setFamilyMemberRelationship("Son");
                      setFamilyMemberNotes("");
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                  >
                    {editingFamilyMemberId ? "Update" : "Add"} Family Member
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
