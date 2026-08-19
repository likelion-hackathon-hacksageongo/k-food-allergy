import { useEffect, useMemo, useRef, useState } from "react";
import { fetchRestaurantsWithMenus } from "./services/menuAnalysis";
import { authenticate, loadProfile, saveProfile } from "./services/account";
import { createFeedback, fetchMyFeedback } from "./services/feedback";
import "./App.css";

const allergyOptions = [
  "Shellfish",
  "Tree nuts",
  "Gluten",
  "Soy",
  "Egg",
  "Dairy",
  "Peanut",
  "Fish",
  "Mollusk",
  "Pork",
  "Beef",
  "Chicken",
  "Sulfites",
  "Buckwheat",
  "Peach",
  "Tomato",
];
const koreanAllergens = {
  Shellfish: "갑각류",
  "Tree nuts": "견과류",
  Gluten: "글루텐",
  Soy: "간장·대두",
  Egg: "계란",
  Dairy: "유제품",
  Peanut: "땅콩",
  Fish: "생선",
  Mollusk: "연체류",
  Pork: "돼지고기",
  Beef: "소고기",
  Chicken: "닭고기",
  Sulfites: "아황산염",
  Buckwheat: "메밀",
  Peach: "복숭아",
  Tomato: "토마토",
};
const apiAllergenKeys = {
  Shellfish: "shellfish",
  "Tree nuts": "nuts",
  Gluten: "wheat",
  Soy: "soy",
  Egg: "egg",
  Dairy: "dairy",
  Peanut: "peanut",
  Fish: "fish",
  Mollusk: "mollusk",
  Pork: "pork",
  Beef: "beef",
  Chicken: "chicken",
  Sulfites: "sulfites",
  Buckwheat: "buckwheat",
  Peach: "peach",
  Tomato: "tomato",
};
const profileLabels = Object.fromEntries(
  Object.entries(apiAllergenKeys).map(([label, key]) => [key, label]),
);
const englishAddresses = {
  "서울특별시 마포구 성미산로 138, 1층 (연남동)":
    "1F, 138 Seongmisan-ro, Mapo-gu, Seoul (Yeonnam-dong)",
  "서울특별시 마포구 연남로 23, 1층 (연남동)":
    "1F, 23 Yeonnam-ro, Mapo-gu, Seoul (Yeonnam-dong)",
  "서울특별시 마포구 와우산로 151, 지1층 (서교동)":
    "B1, 151 Wausan-ro, Mapo-gu, Seoul (Seogyo-dong)",
  "서울특별시 마포구 홍익로5안길 34, 1층 전체호 (서교동)":
    "1F, 34 Hongik-ro 5an-gil, Mapo-gu, Seoul (Seogyo-dong)",
  "서울특별시 마포구 와우산로21길 31-10 (서교동,1층)":
    "1F, 31-10 Wausan-ro 21-gil, Mapo-gu, Seoul (Seogyo-dong)",
  "서울특별시 마포구 월드컵북로 43, 1층 (서교동)":
    "1F, 43 World Cup buk-ro, Mapo-gu, Seoul (Seogyo-dong)",
  "서울특별시 마포구 잔다리로 14, 2층 (서교동)":
    "2F, 14 Jandari-ro, Mapo-gu, Seoul (Seogyo-dong)",
  "서울특별시 마포구 서강로9길 56, 송우빌딩 1층 102호 (창전동)":
    "Room 102, 1F, Songwoo Building, 56 Seogang-ro 9-gil, Mapo-gu, Seoul (Changjeon-dong)",
  "서울특별시 마포구 동교로27길 102, 1층 (연남동)":
    "1F, 102 Donggyo-ro 27-gil, Mapo-gu, Seoul (Yeonnam-dong)",
  "서울특별시 마포구 월드컵북로 9-1, 1층 (서교동)":
    "1F, 9-1 World Cup buk-ro, Mapo-gu, Seoul (Seogyo-dong)",
};
const toEnglishAddress = (address) => englishAddresses[address] || address;
const restaurantFoodEmoji = (restaurant) => {
  const text = `${restaurant.name || ""} ${restaurant.category || ""}`.toLowerCase();
  if (text.includes("gimbap")) return "🍙";
  if (text.includes("samgyetang") || text.includes("dakgalbi")) return "🍗";
  if (text.includes("jokbal") || text.includes("bossam")) return "🍖";
  if (text.includes("kalguksu") || text.includes("noodle")) return "🍜";
  if (text.includes("ssambap")) return "🥬";
  if (text.includes("budae") || text.includes("haejangguk") || text.includes("gukbap") || text.includes("stew")) return "🍲";
  return "🍽️";
};
const getMapStatus = (restaurant) =>
  restaurant.personalizedStatus === "safe" &&
  (restaurant.personalizedCounts?.safe || 0) > 0
    ? "great"
    : "neutral";
const likelihoodPresentation = (allergens = []) => {
  const likelihoods = allergens.map((item) => item.likelihood);
  if (likelihoods.includes("confirmed"))
    return {
      tone: "confirmed",
      label: "confirmed",
      description: "Contains this allergen (90%+ confidence).",
    };
  if (likelihoods.includes("likely"))
    return {
      tone: "warning",
      label: "likely",
      description: "Likely contains this allergen (70–80% confidence).",
    };
  if (likelihoods.includes("possible"))
    return {
      tone: "warning",
      label: "possible",
      description: "May contain this allergen (20–30% confidence).",
    };
  if (likelihoods.includes("none"))
    return {
      tone: "none",
      label: "none",
      description: "Unlikely to contain this allergen.",
    };
  return null;
};
const likelihoodForProfile = (allergens = [], profile = []) => {
  const selectedAllergenKeys = new Set(
    profile.map((item) => apiAllergenKeys[item]).filter(Boolean),
  );
  if (!selectedAllergenKeys.size) return null;
  return likelihoodPresentation(
    allergens.filter((item) => selectedAllergenKeys.has(item.allergen_key)),
  );
};
const supportedLanguages = [
  { code: "ko", label: "한국어" },
  { code: "en", label: "English" },
  { code: "ja", label: "日本語" },
  { code: "zh", label: "中文" },
  { code: "vi", label: "Tiếng Việt" },
  { code: "th", label: "ภาษาไทย" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "ru", label: "Русский" },
  { code: "id", label: "Bahasa Indonesia" },
];
const restaurants = [
  {
    id: "gyeong",
    name: "Yeonnam Hansang",
    type: "Korean home cooking · 4 min walk",
    overall_score: 82,
    status: "great",
    label: "Good match",
    icon: "✓",
    food: "🥗",
    x: "33%",
    y: "25%",
    menus: ["Vegetable bibimbap", "Soy-marinated bulgogi", "Seasonal namul"],
    note: "Two menu options look compatible with your profile.",
    address: "242, Donggyo-ro, Mapo-gu, Seoul",
    image: "Bibimbap",
  },
  {
    id: "dubu",
    name: "Buchang-dong Sundubu",
    type: "Tofu stew · 6 min walk",
    overall_score: 58,
    status: "check",
    label: "Check first",
    icon: "?",
    food: "🍲",
    x: "70%",
    y: "38%",
    menus: ["Mushroom tofu stew", "Plain rice", "Grilled vegetables"],
    note: "Please check the broth and side dishes on site.",
    address: "63, Wausan-ro, Mapo-gu, Seoul",
    image: "Sundubu",
  },
  {
    id: "bbq",
    name: "Yeonnam Meat Garden",
    type: "Korean BBQ · 8 min walk",
    overall_score: 76,
    status: "great",
    label: "Good match",
    icon: "✓",
    food: "🥓",
    x: "51%",
    y: "66%",
    menus: ["Pork belly", "Plain rice", "Lettuce wraps"],
    note: "Staff confirmed an allergen-free dipping sauce.",
    address: "45, Yeonhui-ro 1-gil, Mapo-gu, Seoul",
    image: "Korean BBQ",
  },
  {
    id: "noodle",
    name: "Hongdae Kalguksu",
    type: "Noodles · 9 min walk",
    overall_score: 35,
    status: "risk",
    label: "Caution",
    icon: "!",
    food: "🍜",
    x: "15%",
    y: "69%",
    menus: ["Kalguksu", "Dumplings", "Kimchi"],
    note: "Shellfish may be used in the broth.",
    address: "157, Yanghwa-ro, Mapo-gu, Seoul",
    image: "Kalguksu",
  },
];
const topKFood = [
  {
    id: "bibimbap",
    restaurantId: "gyeong",
    name: "Vegetable bibimbap",
    ingredients: "Rice · spinach · carrot · zucchini · egg",
    checks: ["Egg", "Soy"],
    emoji: "🥗",
    tone: "green",
  },
  {
    id: "bulgogi",
    restaurantId: "gyeong",
    name: "Bulgogi",
    ingredients: "Marinated beef · onion · soy sauce · sesame",
    checks: ["Beef", "Soy"],
    emoji: "🥩",
    tone: "rose",
  },
  {
    id: "japchae",
    restaurantId: "gyeong",
    name: "Japchae",
    ingredients: "Glass noodles · vegetables · soy sauce · sesame",
    checks: ["Soy"],
    emoji: "🍜",
    tone: "orange",
  },
  {
    id: "sundubu",
    restaurantId: "dubu",
    name: "Mushroom sundubu",
    ingredients: "Soft tofu · mushroom · zucchini · broth",
    checks: ["Shellfish", "Soy"],
    emoji: "🍲",
    tone: "orange",
  },
  {
    id: "samgyeopsal",
    restaurantId: "bbq",
    name: "Pork belly with lettuce",
    ingredients: "Pork belly · lettuce · rice · dipping sauce",
    checks: ["Pork", "Soy"],
    emoji: "🥓",
    tone: "rose",
  },
  {
    id: "kimbap",
    restaurantId: "gyeong",
    name: "Vegetable kimbap",
    ingredients: "Rice · seaweed · vegetables · egg",
    checks: ["Egg"],
    emoji: "🍙",
    tone: "green",
  },
  {
    id: "tteokbokki",
    restaurantId: "noodle",
    name: "Tteokbokki",
    ingredients: "Rice cakes · chili paste · fish cake",
    checks: ["Fish", "Wheat", "Soy"],
    emoji: "🌶️",
    tone: "rose",
  },
  {
    id: "dakgalbi",
    restaurantId: "bbq",
    name: "Dakgalbi",
    ingredients: "Chicken · cabbage · chili paste · rice cake",
    checks: ["Soy"],
    emoji: "🍗",
    tone: "orange",
  },
  {
    id: "naengmyeon",
    restaurantId: "noodle",
    name: "Naengmyeon",
    ingredients: "Buckwheat noodles · beef broth · egg",
    checks: ["Beef", "Egg", "Wheat"],
    emoji: "🍜",
    tone: "green",
  },
  {
    id: "kimchi",
    restaurantId: "dubu",
    name: "Kimchi stew",
    ingredients: "Kimchi · tofu · pork · broth",
    checks: ["Pork", "Shellfish", "Soy"],
    emoji: "🥘",
    tone: "rose",
  },
];

function App() {
  const [selectedId, setSelectedId] = useState("gyeong");
  const [profile, setProfile] = useState(() =>
    JSON.parse(localStorage.getItem("kfood-profile") || "[]"),
  );
  const [saved, setSaved] = useState(() =>
    JSON.parse(localStorage.getItem("kfood-saved") || "[]"),
  );
  const [isSignedIn, setIsSignedIn] = useState(() =>
    Boolean(localStorage.getItem("kfood-access-token")),
  );
  const [modal, setModal] = useState(() =>
    localStorage.getItem("kfood-access-token") ? "" : "welcome",
  );
  const [authMode, setAuthMode] = useState("signup");
  const [name, setName] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [email, setEmail] = useState("");
  const [language, setLanguage] = useState(
    () => localStorage.getItem("kfood-language") || "en",
  );
  const [area, setArea] = useState("Hongdae, Seoul");
  const [, setPendingArea] = useState("Hongdae, Seoul");
  const [customArea, setCustomArea] = useState("");
  const [view, setView] = useState(
    () =>
      ({ "/map": "map", "/restaurants": "list", "/feedback": "feedback" })[
        window.location.pathname
      ] || "recommendations",
  );
  const [showQuestion, setShowQuestion] = useState(false);
  const [toast, setToast] = useState("");
  const [menuPhoto, setMenuPhoto] = useState("");
  const [scanComplete, setScanComplete] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [aiMenuIdeas, setAiMenuIdeas] = useState(null);
  const [restaurantVersion, setRestaurantVersion] = useState(0);
  const [profileVersion, setProfileVersion] = useState(0);
  const profileSnapshot = useRef(null);
  const latestProfile = useRef(profile);
  const latestLanguage = useRef(language);
  latestProfile.current = profile;
  latestLanguage.current = language;
  const selected = useMemo(
    () => restaurants.find((item) => item.id === selectedId),
    [selectedId],
  );
  const selectedAllergyNames = profile
    .map((item) => koreanAllergens[item] || item)
    .filter(Boolean);
  const staffQuestion = selectedAllergyNames.length
    ? `이 메뉴나 메뉴의 육수, 양념에 ${selectedAllergyNames.join(", ")} 성분이 들어가나요?`
    : "이 메뉴나 메뉴의 육수, 양념에 알레르기 유발 성분이 들어가나요?";
  restaurants.forEach((restaurant) => {
    restaurant.status = getMapStatus(restaurant);
    restaurant.label =
      restaurant.status === "great"
        ? "Safer to visit"
        : "Information unavailable";
  });
  const recommendedMenus = useMemo(() => {
    const personalizedMenus = restaurants.flatMap((restaurant) =>
      (restaurant.menuDetails || []).map((menu) => ({
        id: menu.id,
        restaurantId: restaurant.id,
        name: menu.name,
        restaurantName: restaurant.name,
        emoji: "🍽️",
        tone: "neutral",
        likelihood: likelihoodForProfile(menu.allergens, profile),
      })),
    );
    if (personalizedMenus.length) {
      const likelihoodOrder = { none: 0, possible: 1, likely: 2, confirmed: 3 };
      return personalizedMenus
        .filter((menu) => menu.likelihood?.label !== "confirmed")
        .sort(
          (a, b) =>
            (likelihoodOrder[a.likelihood?.label] ?? 4) -
            (likelihoodOrder[b.likelihood?.label] ?? 4),
        )
        .slice(0, 5);
    }
    return topKFood.slice(0, 5);
  }, [aiMenuIdeas, profile, restaurantVersion]);
  useEffect(() => {
    if (view !== "recommendations") return;
    document
      .querySelectorAll(".menu-idea-card .likelihood-token")
      .forEach((token) => token.remove());
    document.querySelectorAll(".menu-idea-card").forEach((card, index) => {
      const presentation = recommendedMenus[index]?.likelihood;
      const title = card.querySelector("h3");
      if (!presentation || !title) return;
      const token = document.createElement("span");
      token.className = "likelihood-token";
      token.textContent = presentation.label;
      title.append(token);
    });
  }, [recommendedMenus, view]);

  useEffect(() => {
    localStorage.setItem("kfood-profile", JSON.stringify(profile));
  }, [profile]);
  useEffect(() => {
    localStorage.setItem("kfood-saved", JSON.stringify(saved));
  }, [saved]);
  useEffect(() => {
    localStorage.setItem("kfood-language", language);
  }, [language]);
  useEffect(() => {
    if (!localStorage.getItem("kfood-access-token")) return;
    loadProfile()
      .then((apiProfile) => {
        if (!apiProfile) return;
        setProfile(
          apiProfile.allergens.map((item) => profileLabels[item] || item),
        );
        setLanguage(apiProfile.preferred_language);
      })
      .catch(() => {
        localStorage.removeItem("kfood-access-token");
        localStorage.removeItem("kfood-refresh-token");
        setIsSignedIn(false);
        setModal("welcome");
      });
  }, []);
  useEffect(() => {
    if (modal !== "profile") return;
    profileSnapshot.current = { profile: [...profile], language };
    const restoreProfile = () => {
      if (!profileSnapshot.current) return;
      setProfile(profileSnapshot.current.profile);
      setLanguage(profileSnapshot.current.language);
      profileSnapshot.current = null;
    };
    const handleProfileAction = async (event) => {
      const saveButton = event.target.closest(".primary-button");
      if (saveButton) {
        event.preventDefault();
        event.stopPropagation();
        try {
          await saveProfile(
            latestProfile.current
              .map((item) => apiAllergenKeys[item])
              .filter(Boolean),
            latestLanguage.current,
          );
          profileSnapshot.current = null;
          setModal("");
          setProfileVersion((version) => version + 1);
          setToast("Your food profile has been updated.");
        } catch (error) {
          setToast(error.message);
        }
        return;
      }
      if (
        event.target.closest(".modal-close") ||
        event.target.classList.contains("modal-backdrop")
      )
        restoreProfile();
    };
    document.addEventListener("click", handleProfileAction, true);
    return () =>
      document.removeEventListener("click", handleProfileAction, true);
  }, [modal]);
  useEffect(() => {
    if (modal !== "profile") return;
    const select = document.querySelector(".language-select select");
    if (!select) return;
    select.replaceChildren(
      ...supportedLanguages.map(({ code, label }) => new Option(label, code)),
    );
    select.value = language;
  }, [language, modal]);
  useEffect(() => {
    let active = true;
    fetchRestaurantsWithMenus()
      .then((apiRestaurants) => {
        if (!active || !apiRestaurants?.length) return;
        const mappedRestaurants = apiRestaurants.map((restaurant, index) => ({
          id: String(restaurant.id),
          name: restaurant.name,
          name_ko: restaurant.name_ko,
          type: restaurant.category,
          personalizedStatus: restaurant.personalized?.status,
          personalizedCounts: restaurant.personalized?.counts,
          status: "neutral",
          label: "Check first",
          icon: restaurantFoodEmoji(restaurant),
          food: restaurantFoodEmoji(restaurant),
          x: `${16 + (index % 3) * 33}%`,
          y: `${20 + (Math.floor(index / 3) % 4) * 22}%`,
          menus: restaurant.menus.map((menu) => menu.name),
          menuDetails: restaurant.menus,
          note:
            restaurant.personalized?.reasons?.join(" ") ||
            "",
          address: toEnglishAddress(restaurant.address),
          image: restaurant.category,
        }));
        restaurants.splice(0, restaurants.length, ...mappedRestaurants);
        setSelectedId(mappedRestaurants[0].id);
        setRestaurantVersion((version) => version + 1);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [profile, profileVersion]);
  useEffect(() => {
    if (view !== "detail" || !selected?.menuDetails) return;
    document
      .querySelectorAll(".likelihood-token")
      .forEach((token) => token.remove());
    selected.menuDetails.forEach((menu, index) => {
      const presentation = likelihoodForProfile(menu.allergens, profile);
      if (!presentation) return;
      const row = document.querySelectorAll(".menu-row")[index];
      const title = row?.querySelector("strong");
      const description = row?.querySelector("small");
      if (!title) return;
      const token = document.createElement("span");
      token.className = `likelihood-token ${presentation.tone}`;
      token.textContent = presentation.label;
      title.append(token);
      if (description) description.textContent = presentation.description;
    });
  }, [profile, selected, view, restaurantVersion]);
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(""), 2600);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const path =
      view === "map"
        ? "/map"
        : view === "list"
          ? "/restaurants"
          : view === "detail"
            ? `/restaurants/${selectedId}`
            : view === "feedback"
              ? "/feedback"
              : "/for-you";
    if (window.location.pathname !== path)
      window.history.pushState({}, "", path);
  }, [view, selectedId]);
  useEffect(() => {
    const onPopState = () => {
      const path = window.location.pathname;
      setView(
        path === "/feedback"
          ? "feedback"
          : path === "/map"
            ? "map"
            : path.startsWith("/restaurants/")
              ? "detail"
              : path === "/restaurants"
                ? "list"
                : "recommendations",
      );
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const toggleAllergy = (item) =>
    setProfile((now) =>
      now.includes(item)
        ? now.filter((allergy) => allergy !== item)
        : [...now, item],
    );
  const toggleMapAllergy = async (item) => {
    const nextProfile = profile.includes(item)
      ? profile.filter((allergy) => allergy !== item)
      : [...profile, item];
    setProfile(nextProfile);
    if (!isSignedIn) return;
    try {
      await saveProfile(
        nextProfile.map((allergy) => apiAllergenKeys[allergy]).filter(Boolean),
        language,
      );
      setProfileVersion((version) => version + 1);
    } catch (error) {
      setToast(error.message);
    }
  };
  const openRestaurant = (id) => {
    setSelectedId(id);
    setView("detail");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const toggleSaved = () => {
    const isSaved = saved.includes(selected.id);
    setSaved((now) =>
      isSaved ? now.filter((id) => id !== selected.id) : [...now, selected.id],
    );
    setToast(
      isSaved
        ? "Removed from saved places."
        : `${selected.name} has been saved.`,
    );
  };
  const finishProfile = async () => {
    const password = document.querySelector(
      '.modal input[type="password"]',
    )?.value;
    const enteredEmail =
      email.trim() ||
      document.querySelector('.modal input[type="email"]')?.value?.trim() ||
      "";
    const username = authMode === "signup" ? name.trim() : loginUsername.trim();
    const enteredUsername =
      username ||
      (authMode === "signin"
        ? document.querySelector(".modal .name-input input")?.value?.trim()
        : "");
    if (
      !enteredUsername ||
      !password ||
      (authMode === "signup" && !enteredEmail)
    ) {
      setToast(
        authMode === "signup"
          ? "Enter a username, email, and password."
          : "Enter your username and password.",
      );
      return;
    }
    if (authMode === "signup" && !profile.length) {
      setToast("Please select at least one allergy or dietary restriction.");
      return;
    }
    try {
      const session = await authenticate(
        authMode,
        enteredUsername,
        enteredEmail,
        password,
      );
      localStorage.setItem("kfood-access-token", session.access);
      localStorage.setItem("kfood-refresh-token", session.refresh);
      localStorage.setItem("kfood-user-email", enteredEmail || enteredUsername);
      const apiProfile =
        authMode === "signup"
          ? await saveProfile(
              profile.map((item) => apiAllergenKeys[item]).filter(Boolean),
              language,
            )
          : await loadProfile();
      setProfile(
        apiProfile.allergens.map((item) => profileLabels[item] || item),
      );
      setLanguage(apiProfile.preferred_language);
      setProfileVersion((version) => version + 1);
      setIsSignedIn(true);
      setModal("");
      setView("recommendations");
      setToast(
        authMode === "signin"
          ? "Welcome back. Your food profile has been loaded."
          : "Your food profile is saved. Here are your recommendations.",
      );
    } catch (error) {
      setToast(error.message);
    }
  };
  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setToast(
        "Location is not supported in this browser. Please enter an area instead.",
      );
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const location = `Current location · ${coords.latitude.toFixed(3)}, ${coords.longitude.toFixed(3)}`;
        setArea(location);
        setModal("");
        setToast("Your current GPS location has been applied.");
      },
      () =>
        setToast(
          "We could not access your location. Please allow location permission or enter an area.",
        ),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };
  const addCustomArea = () => {
    const value = customArea.trim();
    if (!value) return;
    setArea(value);
    setCustomArea("");
    setModal("");
    setToast(`Area changed to ${value}.`);
  };
  const selectMenuPhoto = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setMenuPhoto(URL.createObjectURL(file));
    setScanLoading(true);
    setScanResult(null);

    try {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("allergens", profile.map((item) => apiAllergenKeys[item]).filter(Boolean).join(","));
      formData.append("language", language || "en");

      const res = await fetch("http://localhost:8100/scan/full", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        console.error("[Scan Error]", res.status, errText);
        throw new Error("Scan failed");
      }
      const data = await res.json();
      setScanResult(data);
    } catch (e) {
      console.error("[Scan Exception]", e);
      setScanResult(null);
      setToast("Menu scan failed. Check console for details.");
    } finally {
      setScanLoading(false);
      setScanComplete(true);
    }
  };

  if (view === "feedback" && isSignedIn)
    return (
      <FeedbackPage
        onNavigate={setView}
        onProfile={() => setModal("profile")}
      />
    );
  return (
    <main className="app-shell">
      <nav className="topbar">
        <a className="brand" href="#top">
          <span className="brand-mark">K</span>
          <span>K-Food Map</span>
        </a>
        <div className="nav-links">
          <button
            className={view === "recommendations" ? "active" : ""}
            onClick={() => setView("recommendations")}
          >
            🍽️ For you
          </button>
          <button
            className={view === "map" ? "active" : ""}
            onClick={() => setView("map")}
          >
            🗺️ Explore map
          </button>
          <button
            className={view === "list" ? "active" : ""}
            onClick={() => setView("list")}
          >
            🍴 Restaurants
          </button>
          <button
            className={view === "feedback" ? "active" : ""}
            onClick={() => setView("feedback")}
          >
            Feedback
          </button>
          <button onClick={() => setModal("profile")}>My profile</button>
        </div>
        <button className="avatar" onClick={() => setModal("profile")}>
          {name ? name[0].toUpperCase() : "Me"}
        </button>
      </nav>

      {view === "recommendations" && (
        <section className="hero-section" id="top">
          <div className="eyebrow">
            <span></span> Your personal Korean food map
          </div>
          <h1>
            Korean food,
            <br />
            <em>made safer for you.</em>
          </h1>
          <p>
            Add your allergies and dietary needs to discover Korean restaurants
            and menus that fit the way you eat.
          </p>
          <button
            className="scan-cta"
            onClick={() => {
              setScanComplete(false);
              setModal("scan");
            }}
          >
            <span>⌑</span>
            <span>
              <b>Scan a menu photo</b>
              <small>Translate a menu and check ingredients</small>
            </span>
            <i>→</i>
          </button>
        </section>
      )}

      <section
        className={`map-layout page-section ${view === "map" ? "" : "view-hidden"}`}
        id="map"
      >
        <aside className="side-panel">
          <div className="panel-heading">
            <div>
              <p className="overline">Map</p>
              <h2>Restaurant recommendations</h2>
            </div>
          </div>
          <p className="panel-copy">
            We recommend nearby restaurants that match your dietary needs.
          </p>
          <div className="map-location">
            <strong>{area}</strong>
            <button onClick={() => setModal("area")}>Change search area →</button>
          </div>
          <div className="filter-list">
            {profile.length ? (
              profile.map((item) => (
                <button
                  key={item}
                  className="filter-chip on"
                  onClick={() => toggleMapAllergy(item)}
                >
                  <span>◌</span>
                  {item}
                  <b>×</b>
                </button>
              ))
            ) : (
              <p className="empty-profile">No dietary information added yet.</p>
            )}
          </div>
          <button
            className="add-preference"
            onClick={() => setModal("profile")}
          >
            + Add allergies or dietary needs
          </button>
          <div className="map-guide" aria-label="Map guide">
            <p className="map-guide-green">● Green: Safer to eat</p>
            <p className="map-guide-gray">● Gray: Unknown</p>
          </div>
          <div className="legend">
            <p className="overline">Map guide</p>
            <div>
              <i className="dot great"></i> Good match{" "}
              <small>enough menu information</small>
            </div>
            <div>
              <i className="dot check"></i> Check first{" "}
              <small>some details are missing</small>
            </div>
            <div>
              <i className="dot risk"></i> Caution{" "}
              <small>likely allergen conflict</small>
            </div>
          </div>
        </aside>
        <div className="map-area">
          <div className="map-toolbar">
            <button
              className="area-button"
              onClick={() => {
                setPendingArea(area);
                setModal("area");
              }}
            >
              <span>⌖</span> {area} <b>⌄</b>
            </button>
            <button
              className="map-control"
              onClick={() => setToast(`Your location is set to ${area}.`)}
            >
              ◎
            </button>
          </div>
          <div className="city-map">
            <div className="river"></div>
            <div className="road road-one"></div>
            <div className="road road-two"></div>
            <div className="road road-three"></div>
            <span className="map-label hongik">Hongik University</span>
            <span className="map-label seogyo">Seogyo-dong</span>
            <span className="map-label yeonnam">Yeonnam-dong</span>
            {restaurants.map((item) => (
              <div
                key={item.id}
                className="map-pin-wrap"
                style={{ left: item.x, top: item.y }}
              >
                <button
                  className={`map-pin ${item.status} ${selectedId === item.id ? "selected" : ""}`}
                  onClick={() => openRestaurant(item.id)}
                  aria-label={`View ${item.name}`}
                >
                  {item.food}
                </button>
                <span>
                  <b>{item.menus[0]}</b>
                  {item.name}
                </span>
              </div>
            ))}
            <div className="you-are-here">
              <span></span> You are here
            </div>
          </div>
          <button className="next-step" onClick={() => setView("list")}>
            See restaurants in a list →
          </button>
        </div>
      </section>

      <section
        className={`results-section page-section ${view === "recommendations" ? "home-dashboard" : ""} ${view === "recommendations" || view === "list" ? "" : "view-hidden"}`}
      >
        <div className="results-top">
          <div>
            <p className="overline">
              {view === "recommendations"
                ? "K-Food top 10 · personalized for you"
                : "Korean restaurants nearby"}
            </p>
            <h2>
              {view === "recommendations"
                ? "Korean food ideas for you"
                : "Picked for you"}
            </h2>
            {view === "recommendations" && (
              <div className="applied-profile">
                <span>Based on your profile</span>
                {profile.length ? (
                  profile.map((item) => <b key={item}>◌ {item}</b>)
                ) : (
                  <button onClick={() => setModal("profile")}>
                    Add allergy information
                  </button>
                )}
              </div>
            )}
          </div>
          {view === "list" && (
            <button className="see-all" onClick={() => setView("map")}>
              Explore map <span>→</span>
            </button>
          )}
        </div>
        <div
          className={`restaurant-grid ${view === "recommendations" ? "menu-idea-grid" : ""}`}
        >
          {view === "recommendations"
            ? recommendedMenus.length ? recommendedMenus.map((idea) => (
                <button
                  className={`menu-idea-card ${idea.tone}`}
                  key={idea.id}
                  onClick={() => openRestaurant(idea.restaurantId)}
                >
                  <div className="dish-image">
                    <span>{idea.emoji}</span>
                  </div>
                  <div className="dish-copy">
                    <h3>{idea.name}</h3>
                    <p>
                      {idea.restaurantName ||
                        restaurants.find((restaurant) => restaurant.id === idea.restaurantId)
                          ?.name ||
                        "Restaurant"}
                    </p>
                  </div>
                  <span className="chevron">→</span>
                </button>
              )) : (
                <p className="menu-idea-empty">
                  No lower-risk menu ideas are available for your current profile.
                </p>
              )
            : [...restaurants]
                .sort(
                  (a, b) =>
                    Number(b.status === "great") - Number(a.status === "great"),
                )
                .map((item) => (
                <button
                  className={`restaurant-card ${selectedId === item.id ? "current" : ""}`}
                  key={item.id}
                  onClick={() => openRestaurant(item.id)}
                >
                  <div className={`status-icon ${item.status}`}>
                    {item.food}
                  </div>
                  <div className="restaurant-main">
                    <div className="restaurant-title">
                      <h3>{item.name}</h3>
                      <span className={`status-pill ${item.status}`}>
                        {item.label}
                      </span>
                    </div>
                    <p>{item.type}</p>
                    <div className="menu-tags">
                      {item.menus.slice(0, 2).map((menu) => (
                        <span key={menu}>{menu}</span>
                      ))}
                    </div>
                  </div>
                  <span className="chevron">→</span>
                </button>
              ))}
        </div>
        {view === "recommendations" && (
          <section className="home-saved">
            <div className="saved-heading">
              <div>
                <p className="overline">Saved list</p>
                <h2>Keep your safe picks close</h2>
              </div>
            </div>
            {saved.length ? (
              <div className="saved-home-grid">
                {restaurants
                  .filter((item) => saved.includes(item.id))
                  .map((item) => (
                    <button
                      key={item.id}
                      onClick={() => openRestaurant(item.id)}
                    >
                      <span className={`status-icon ${item.status}`}>
                        {item.icon}
                      </span>
                      <span>
                        <b>{item.name}</b>
                        <small>{item.menus[0]}</small>
                      </span>
                      <i>→</i>
                    </button>
                  ))}
              </div>
            ) : (
              <div className="saved-home-empty">
                No saved places yet. Open a restaurant and tap the heart to save
                it here.
              </div>
            )}
          </section>
        )}
      </section>

      <section
        className={`detail-section page-section ${view === "detail" ? "" : "view-hidden"}`}
        id="restaurant-detail"
      >
        <div className="detail-intro">
          <button className="back-button" onClick={() => setView("list")}>
            ← Back to restaurants
          </button>
          <p className="overline">Restaurant and menu details</p>
          <h2>{selected.name}</h2>
          <p>{selected.type}</p>
          <p className="address">⌖ {selected.address}</p>
          <button
            className={`heart-button ${saved.includes(selected.id) ? "saved" : ""}`}
            onClick={toggleSaved}
            aria-label={
              saved.includes(selected.id)
                ? "Remove from saved"
                : "Save restaurant"
            }
          >
            {saved.includes(selected.id) ? "♥" : "♡"}
            <span>
              {saved.includes(selected.id) ? "Saved" : "Save restaurant"}
            </span>
          </button>
        </div>
        <div className="detail-card">
          <div className="detail-status">
            <span className={`status-icon ${selected.status}`}>
              {selected.icon}
            </span>
            <div>
              <span className={`status-pill ${selected.status}`}>
                {selected.label}
              </span>
              {selected.note && <h3>{selected.note}</h3>}
            </div>
          </div>
          <div className="detail-content">
            <div>
              <p className="overline">Menu ideas for you</p>
              <div className="likelihood-guide" aria-label="Allergen token guide">
                <p><b>confirmed</b> Contains this allergen (90%+ confidence).</p>
                <p><b>likely</b> Likely contains this allergen (70–80% confidence).</p>
                <p><b>possible</b> May contain this allergen (20–30% confidence).</p>
                <p><b>none</b> Unlikely to contain this allergen.</p>
              </div>
              {selected.menus.map((menu, index) => (
                <div className="menu-row" key={menu}>
                  <span className={index === 0 ? "checkmark" : "soft-check"}>
                    {index === 0 ? "✓" : "·"}
                  </span>
                  <strong>{menu}</strong>
                </div>
              ))}
            </div>
            <div className="insight">
              <p className="overline">K-food ingredient insight</p>
              <p>
                {selectedAllergyNames.length
                  ? `Menu tokens are filtered for your profile: ${selectedAllergyNames.join(", ")}.`
                  : "Add allergies to your profile to see personalized menu tokens."}
              </p>
              <button onClick={() => setShowQuestion(!showQuestion)}>
                {showQuestion ? "Hide Korean question" : "Show Korean question"}{" "}
                <span>→</span>
              </button>
              {showQuestion && (
                <div className="korean-question">
                  <b>Show this to staff</b>
                  <br />{staffQuestion}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
      <footer>
        <div className="brand">
          <span className="brand-mark">K</span>
          <span>K-Food Map</span>
        </div>
        <p>Explore Korean food for your needs.</p>
      </footer>
      <nav className="mobile-nav" aria-label="Mobile navigation">
        <button
          className={view === "recommendations" ? "active" : ""}
          onClick={() => {
            setView("recommendations");
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          <span>✦</span>For you
        </button>
        <button
          className={view === "map" ? "active" : ""}
          onClick={() => {
            setView("map");
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          <span>⌖</span>Map
        </button>
        <button
          className={view === "list" ? "active" : ""}
          onClick={() => {
            setView("list");
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          <span>☷</span>Places
        </button>
        <button
          className={view === "feedback" ? "active" : ""}
          onClick={() => setView("feedback")}
        >
          <span>✎</span>Feedback
        </button>
      </nav>
      {toast && <div className="toast">✓ {toast}</div>}
      {modal === "scan" && (
        <div className="modal-backdrop">
          <div className="modal scan-modal">
            <button className="modal-close" onClick={() => setModal("")}>
              ×
            </button>
            <span className="modal-kicker">MENU PHOTO CHECK</span>
            <h2>
              Scan, translate,
              <br />
              and ask with confidence.
            </h2>
            {!scanComplete ? (
              <label className="photo-drop">
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={selectMenuPhoto}
                />
                <span>⌑</span>
                <b>Take or choose a menu photo</b>
                <small>JPG, PNG, or HEIC</small>
              </label>
            ) : scanLoading ? (
              <div className="scan-result">
                <img src={menuPhoto} alt="Uploaded menu" />
                <div className="scan-copy" style={{textAlign:"center",padding:"30px 0"}}>
                  <div style={{width:"40px",height:"40px",margin:"0 auto 16px",border:"3px solid #e5e7eb",borderTop:"3px solid #2f6b43",borderRadius:"50%",animation:"spin 1s linear infinite"}}></div>
                  <p className="overline">Analyzing menu...</p>
                  <p style={{color:"#666",fontSize:"14px"}}>Translating and checking allergens.<br/>This may take 5-10 seconds.</p>
                </div>
              </div>
            ) : scanResult ? (
              <div className="scan-result">
                <img src={menuPhoto} alt="Uploaded menu" />
                <div className="scan-copy">
                  <p className="overline">Translation & allergen check — {scanResult.total_items} items found</p>
                  {scanResult.intro_text && (
                    <div className="staff-phrase">
                      <b>Show this to staff first</b>
                      <p style={{margin:"6px 0",fontSize:"15px"}}>{scanResult.intro_text}</p>
                    </div>
                  )}
                  {scanResult.menu_items.map((item, i) => (
                    <div key={i} style={{margin:"12px 0",padding:"10px",borderRadius:"8px",background: item.safety_level === "danger" ? "#fef2f2" : item.safety_level === "caution" ? "#fefce8" : "#f0fdf4"}}>
                      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                        <strong>{item.translated_name}</strong>
                        <span style={{fontSize:"11px",padding:"2px 6px",borderRadius:"4px",background: item.safety_level === "danger" ? "#fca5a5" : item.safety_level === "caution" ? "#fde047" : "#86efac"}}>
                          {item.safety_level === "danger" ? "⚠ Danger" : item.safety_level === "caution" ? "? Check" : "✓ Safe"}
                        </span>
                      </div>
                      <small style={{color:"#666"}}>{item.original_text} {item.price && `· ${item.price}`}</small>
                      {item.description && <p style={{margin:"4px 0",fontSize:"13px"}}>{item.description}</p>}
                      {item.allergen_warnings.map((w, j) => (
                        <p key={j} style={{margin:"2px 0",fontSize:"12px",color:"#b91c1c"}}>⚠ {w}</p>
                      ))}
                      {item.staff_query && (
                        <div style={{marginTop:"6px",padding:"6px 8px",background:"#fff",borderRadius:"4px",border:"1px solid #e5e7eb"}}>
                          <small style={{color:"#888"}}>Show to staff:</small>
                          <p style={{margin:"2px 0",fontSize:"14px",fontWeight:"500"}}>{item.staff_query}</p>
                          <small style={{color:"#666"}}>{item.query_explanation}</small>
                        </div>
                      )}
                    </div>
                  ))}
                  <p style={{fontSize:"11px",color:"#888",marginTop:"12px"}}>{scanResult.disclaimer}</p>
                </div>
              </div>
            ) : (
              <div className="scan-result">
                <img src={menuPhoto} alt="Uploaded menu" />
                <div className="scan-copy">
                  <p className="overline">Scan failed</p>
                  <p>Could not analyze the menu. Please try again with a clearer photo.</p>
                </div>
              </div>
            )}
            <button className="primary-button" onClick={() => setModal("")}>
              {scanComplete ? "Done" : "Close"}
            </button>
          </div>
        </div>
      )}
      {modal && modal !== "scan" && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && modal !== "welcome")
              setModal("");
          }}
        >
          <div className="modal" role="dialog" aria-modal="true">
            <button
              className="modal-close"
              onClick={() => (modal === "welcome" ? null : setModal(""))}
            >
              ×
            </button>
            {modal === "welcome" && (
              <>
                <span className="modal-kicker">WELCOME TO K-FOOD MAP</span>
                <h2>
                  {authMode === "signup" ? (
                    <>
                      Create your account
                      <br />
                      and food profile.
                    </>
                  ) : (
                    <>Welcome back.</>
                  )}
                </h2>
                <p>
                  {authMode === "signup"
                    ? "Start with your account details, then add what you need to avoid."
                    : "Sign in to continue with your saved allergies, dietary preferences, and places."}
                </p>
                <div className="auth-tabs">
                  <button
                    className={authMode === "signup" ? "on" : ""}
                    onClick={() => setAuthMode("signup")}
                  >
                    Sign up
                  </button>
                  <button
                    className={authMode === "signin" ? "on" : ""}
                    onClick={() => setAuthMode("signin")}
                  >
                    Sign in
                  </button>
                </div>
                {authMode === "signup" && (
                  <label className="name-input">
                    Username
                    <input
                      placeholder="e.g. alice"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </label>
                )}
                {authMode === "signup" ? (
                  <label className="name-input">
                    Email address
                    <input type="email" placeholder="alice@example.com" />
                  </label>
                ) : (
                  <label className="name-input">
                    Username
                    <input
                      placeholder="Your username"
                      value={loginUsername}
                      onChange={(e) => setLoginUsername(e.target.value)}
                    />
                  </label>
                )}
                <label className="name-input">
                  Password
                  <input type="password" placeholder="At least 8 characters" />
                </label>
                {authMode === "signup" ? (
                  <AllergyEditor profile={profile} onToggle={toggleAllergy} />
                ) : (
                  <div className="sign-in-profile">
                    <span>✓</span>
                    <div>
                      <b>Food profile ready</b>
                      <p>
                        {profile.length
                          ? `${profile.join(", ")} will be applied after sign in.`
                          : "Your saved allergies and dietary preferences will be loaded."}
                      </p>
                    </div>
                  </div>
                )}
                <button className="primary-button" onClick={finishProfile}>
                  {authMode === "signup"
                    ? "Create account and continue"
                    : "Sign in and load my profile"}{" "}
                  →
                </button>
              </>
            )}
            {modal === "area" && (
              <>
                <span className="modal-kicker">CHOOSE AN AREA</span>
                <h2>
                  Where would you
                  <br />
                  like to eat?
                </h2>
                <p>
                  Use your phone or browser location, choose a neighborhood, or
                  add your own destination.
                </p>
                <button className="gps-button" onClick={useCurrentLocation}>
                  ⌖ Use my current location
                </button>
                <div className="custom-area">
                  <input
                    value={customArea}
                    onChange={(event) => setCustomArea(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") addCustomArea();
                    }}
                    placeholder="Enter a neighborhood or address"
                  />
                  <button onClick={addCustomArea} disabled={!customArea.trim()}>
                    Add
                  </button>
                </div>
                <div className="area-options">
                  {[
                    "Hongdae, Seoul",
                    "Myeongdong, Seoul",
                    "Jongno, Seoul",
                    "Gangnam, Seoul",
                    "Itaewon, Seoul",
                  ].map((item) => (
                    <button
                      className={area === item ? "selected" : ""}
                      key={item}
                      onClick={() => {
                        setArea(item);
                        setModal("");
                        setToast(`Area changed to ${item}.`);
                      }}
                    >
                      {item}
                      <span>→</span>
                    </button>
                  ))}
                </div>
              </>
            )}
            {modal === "profile" && (
              <>
                <span className="modal-kicker">MY PROFILE</span>
                <h2>
                  Update your food
                  <br />
                  preferences.
                </h2>
                <p>Your map and recommendations update as soon as you save.</p>
                <label className="language-select">
                  Display language
                  <select
                    value={language}
                    onChange={(event) => {
                      setLanguage(event.target.value);
                      setToast(
                        event.target.value === "en"
                          ? "Display language set to English."
                          : "Korean is selected. More languages are coming soon.",
                      );
                    }}
                  >
                    <option value="en">English</option>
                    <option value="ko">한국어 (coming soon)</option>
                    <option disabled>日本語 (coming soon)</option>
                    <option disabled>中文 (coming soon)</option>
                    <option disabled>Español (coming soon)</option>
                  </select>
                </label>
                <AllergyEditor profile={profile} onToggle={toggleAllergy} />
                <button
                  className="primary-button"
                  onClick={() => {
                    setModal("");
                    setToast("Your food profile has been updated.");
                  }}
                >
                  Save changes →
                </button>
              </>
            )}
            {modal === "saved" && (
              <>
                <span className="modal-kicker">SAVED PLACES</span>
                <h2>
                  Restaurants and menus
                  <br />
                  to revisit.
                </h2>
                {saved.length ? (
                  <div className="saved-list">
                    {restaurants
                      .filter((item) => saved.includes(item.id))
                      .map((item) => (
                        <button
                          key={item.id}
                          onClick={() => {
                            setSelectedId(item.id);
                            setModal("");
                            setView("detail");
                          }}
                        >
                          <span className={`status-icon ${item.status}`}>
                            {item.icon}
                          </span>
                          <span>
                            <b>{item.name}</b>
                            <small>
                              {item.menus[0]} · {item.type}
                            </small>
                          </span>
                          <i>→</i>
                        </button>
                      ))}
                  </div>
                ) : (
                  <div className="saved-empty">
                    You have no saved restaurants yet.
                    <br />
                    Tap the heart on a restaurant you like.
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

function FeedbackPage({ onNavigate, onProfile }) {
  const onBack = () => onNavigate("recommendations");
  const [restaurants, setRestaurants] = useState([]);
  const [feedbacks, setFeedbacks] = useState([]);
  const [restaurantId, setRestaurantId] = useState("");
  const [menuName, setMenuName] = useState("");
  const [staffInfo, setStaffInfo] = useState("unsure");
  const [modification, setModification] = useState("unsure");
  const [matched, setMatched] = useState("unsure");
  const [hadReaction, setHadReaction] = useState(false);
  const [reactionDescription, setReactionDescription] = useState("");
  const [message, setMessage] = useState("");

  const refresh = async () => {
    const [restaurantData, feedbackData] = await Promise.all([
      fetchRestaurantsWithMenus(),
      fetchMyFeedback(),
    ]);
    setRestaurants(restaurantData || []);
    setFeedbacks(feedbackData || []);
  };
  useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, []);
  const selectedRestaurant = restaurants.find(
    (restaurant) => String(restaurant.id) === restaurantId,
  );
  const submit = async (event) => {
    event.preventDefault();
    if (!restaurantId) {
      setMessage("Choose the restaurant you visited.");
      return;
    }
    const matchingMenu = selectedRestaurant?.menus.find(
      (menu) => menu.name.trim().toLowerCase() === menuName.trim().toLowerCase(),
    );
    try {
      await createFeedback({
        restaurant: Number(restaurantId),
        menu_item: matchingMenu?.id || null,
        staff_provided_info: staffInfo,
        staff_offered_modification: modification,
        info_matched_reality: matched,
        had_reaction: hadReaction,
        reaction_description: reactionDescription,
      });
      setMessage("Your visit feedback has been saved.");
      setMenuName("");
      setHadReaction(false);
      setReactionDescription("");
      refresh();
    } catch (error) {
      setMessage(error.message);
    }
  };
  return (
    <main className="feedback-page">
      <nav className="topbar">
        <a className="brand" href="#top" onClick={onBack}>
          <span className="brand-mark">K</span>
          <span>K-Food Map</span>
        </a>
        <div className="nav-links">
          <button onClick={() => onNavigate("recommendations")}>🍽️ For you</button>
          <button onClick={() => onNavigate("map")}>🗺️ Explore map</button>
          <button onClick={() => onNavigate("list")}>🍴 Restaurants</button>
          <button className="active">Feedback</button>
          <button onClick={onProfile}>My profile</button>
        </div>
        <button className="avatar" onClick={onProfile}>Me</button>
      </nav>
      <section className="feedback-content">
        <div>
          <p className="overline">MY VISIT RECORDS</p>
          <h1>Share what you learned.</h1>
          <p>
            Your feedback helps build practical information so people with
            similar dietary needs can choose and ask with more confidence.
          </p>
        </div>
        <div className="feedback-layout">
          <form className="feedback-form" onSubmit={submit}>
            <h2>Add a visit</h2>
            <label>
              Restaurant
              <select
                value={restaurantId}
                onChange={(event) => {
                  setRestaurantId(event.target.value);
                  setMenuName("");
                }}
              >
                <option value="">Choose a restaurant</option>
                {restaurants.map((restaurant) => (
                  <option key={restaurant.id} value={restaurant.id}>
                    {restaurant.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Menu (optional)
              <input
                value={menuName}
                onChange={(event) => setMenuName(event.target.value)}
                placeholder="e.g. Bibimbap"
              />
            </label>
            <label>
              Did staff provide ingredient information?
              <select
                value={staffInfo}
                onChange={(event) => setStaffInfo(event.target.value)}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unsure">Not sure</option>
              </select>
            </label>
            <label>
              Was a modification offered?
              <select
                value={modification}
                onChange={(event) => setModification(event.target.value)}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unsure">Not sure</option>
              </select>
            </label>
            <label>
              Did the information match your visit?
              <select
                value={matched}
                onChange={(event) => setMatched(event.target.value)}
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unsure">Not sure</option>
              </select>
            </label>
            <label className="reaction-check">
              <input
                type="checkbox"
                checked={hadReaction}
                onChange={(event) => setHadReaction(event.target.checked)}
              />{" "}
              I had an allergic reaction
            </label>
            {hadReaction && (
              <label>
                What happened?
                <textarea
                  value={reactionDescription}
                  onChange={(event) =>
                    setReactionDescription(event.target.value)
                  }
                />
              </label>
            )}
            <button className="primary-button" type="submit">
              Save visit feedback
            </button>
            {message && <p className="feedback-message">{message}</p>}
          </form>
          <section className="feedback-list">
            <h2>My feedback</h2>
            {feedbacks.length ? (
              feedbacks.map((feedback) => (
                <article key={feedback.id}>
                  <b>Restaurant #{feedback.restaurant}</b>
                  <p>
                    Staff information:{" "}
                    {feedback.staff_provided_info || "Not recorded"}
                  </p>
                  <p>
                    Modification offered:{" "}
                    {feedback.staff_offered_modification || "Not recorded"}
                  </p>
                  <p>
                    {feedback.had_reaction
                      ? `Reaction reported: ${feedback.reaction_description || "No details"}`
                      : "No reaction reported"}
                  </p>
                  <small>
                    {new Date(feedback.created_at).toLocaleDateString()}
                  </small>
                </article>
              ))
            ) : (
              <p className="feedback-empty">No visit feedback yet.</p>
            )}
          </section>
        </div>
      </section>
      <nav className="mobile-nav" aria-label="Mobile navigation">
        <button onClick={() => onNavigate("recommendations")}>
          <span>✦</span>For you
        </button>
        <button onClick={() => onNavigate("map")}>
          <span>⌖</span>Map
        </button>
        <button onClick={() => onNavigate("list")}>
          <span>☷</span>Places
        </button>
        <button className="active" onClick={() => onNavigate("feedback")}>
          <span>✎</span>Feedback
        </button>
      </nav>
    </main>
  );
}

function AllergyEditor({ profile, onToggle }) {
  const [customAllergy, setCustomAllergy] = useState("");
  const addCustomAllergy = () => {
    const value = customAllergy.trim();
    if (value && !profile.includes(value)) onToggle(value);
    setCustomAllergy("");
  };
  return (
    <div className="allergy-editor">
      <p>Select allergies or dietary restrictions</p>
      <div>
        {[
          ...allergyOptions,
          ...profile.filter((item) => !allergyOptions.includes(item)),
        ].map((item) => (
          <button
            key={item}
            className={profile.includes(item) ? "selected" : ""}
            onClick={() => onToggle(item)}
          >
            {profile.includes(item) ? "✓ " : "+ "}
            {item}
          </button>
        ))}
      </div>
      <div className="custom-allergy">
        <input
          value={customAllergy}
          onChange={(event) => setCustomAllergy(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addCustomAllergy();
            }
          }}
          placeholder="Add your own (e.g. sesame, peach)"
          aria-label="Add a custom allergy"
        />
        <button onClick={addCustomAllergy} disabled={!customAllergy.trim()}>
          Add
        </button>
      </div>
    </div>
  );
}
function StaffQuestion({ profile }) {
  const ingredients = profile
    .map((item) => koreanAllergens[item] || item)
    .join(", ");
  return (
    <p>
      이 메뉴에 {ingredients || "알레르기 유발 재료"}가 들어가나요? 육수, 소스,
      반찬에도 포함되어 있는지 확인 부탁드립니다.
    </p>
  );
}
function KoreanAllergenList({ profile }) {
  const ingredients = profile.map((item) => koreanAllergens[item] || item);
  return (
    <div className="scan-allergens">
      <b>알레르기 유발 재료</b>
      <p>
        {ingredients.length
          ? ingredients.join(", ")
          : "등록된 알레르기 정보가 없습니다."}
      </p>
    </div>
  );
}
export default App;
