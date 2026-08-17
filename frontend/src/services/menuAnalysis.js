/**
 * Frontend contract for the future Django + AI menu-analysis endpoint.
 * Expected response: { menus: [{ id, restaurantId, name, ingredients, emoji, tone }] }
 */
export async function fetchPersonalizedMenuIdeas(profile) {
  const response = await fetch("/api/ai/menu-recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ allergies: profile }),
  });

  if (!response.ok) throw new Error("Menu analysis is unavailable");
  return response.json();
}
