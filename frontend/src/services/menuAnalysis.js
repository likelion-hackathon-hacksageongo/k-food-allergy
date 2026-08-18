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
  const restaurants = Array.isArray(restaurantResponse)
    ? restaurantResponse
    : restaurantResponse?.results;
  if (!restaurants) return null;

  return Promise.all(
    restaurants.map(async (restaurant) => {
      const menuResponse = await fetchJson(
        `/api/menus/?restaurant=${restaurant.id}`,
      );
      return {
        ...restaurant,
        menus: Array.isArray(menuResponse)
          ? menuResponse
          : menuResponse?.results || [],
      };
    }),
  );
}
