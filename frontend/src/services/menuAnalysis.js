/**
 * Django proxies the AI server. The batch endpoint returns the lightweight
 * restaurant summaries used to colour map pins by `overall_score`.
 */
const menuRecommendationsEndpoint = import.meta.env.VITE_MENU_RECOMMENDATIONS_ENDPOINT || "/api/analysis/batch/";
const restaurantsEndpoint = "/api/restaurants/";

function authHeaders() {
  const accessToken = localStorage.getItem("kfood-access-token");
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : null;
}

async function fetchJson(url) {
  const headers = authHeaders();
  if (!headers) return null;
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error("Restaurant data is unavailable");
  return response.json();
}

export async function fetchRestaurantsWithMenus() {
  const restaurantResponse = await fetchJson(restaurantsEndpoint);
  const restaurants = Array.isArray(restaurantResponse) ? restaurantResponse : restaurantResponse?.results;
  if (!restaurants) return null;

  return Promise.all(restaurants.map(async (restaurant) => {
    const menuResponse = await fetchJson(`/api/menus/?restaurant=${restaurant.id}`);
    return {
      ...restaurant,
      menus: Array.isArray(menuResponse) ? menuResponse : menuResponse?.results || [],
    };
  }));
}

export async function fetchPersonalizedMenuIdeas() {
  const headers = authHeaders();
  if (!headers) return null;

  const response = await fetch(menuRecommendationsEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) throw new Error("Restaurant analysis is unavailable");
  return response.json();
}
