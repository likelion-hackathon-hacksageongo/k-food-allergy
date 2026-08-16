import { useEffect, useMemo, useState } from "react";
import "./App.css";

const allergyOptions = [
  "Shellfish",
  "Dairy",
  "Peanut",
  "Tree nuts",
  "Egg",
  "Fish",
  "Gluten",
  "Soy",
  "Pork",
  "Beef",
];
const restaurants = [
  { id: "gyeong", name: "Yeonnam Hansang", type: "Korean home cooking · 4 min walk", status: "great", label: "Good match", icon: "✓", food: "🥗", x: "33%", y: "25%", menus: ["Vegetable bibimbap", "Soy-marinated bulgogi", "Seasonal namul"], note: "Two menu options look compatible with your profile.", address: "242, Donggyo-ro, Mapo-gu, Seoul", image: "Bibimbap" },
  { id: "dubu", name: "Buchang-dong Sundubu", type: "Tofu stew · 6 min walk", status: "check", label: "Check first", icon: "?", food: "🍲", x: "70%", y: "38%", menus: ["Mushroom tofu stew", "Plain rice", "Grilled vegetables"], note: "Please check the broth and side dishes on site.", address: "63, Wausan-ro, Mapo-gu, Seoul", image: "Sundubu" },
  { id: "bbq", name: "Yeonnam Meat Garden", type: "Korean BBQ · 8 min walk", status: "great", label: "Good match", icon: "✓", food: "🥓", x: "51%", y: "66%", menus: ["Pork belly", "Plain rice", "Lettuce wraps"], note: "Staff confirmed an allergen-free dipping sauce.", address: "45, Yeonhui-ro 1-gil, Mapo-gu, Seoul", image: "Korean BBQ" },
  { id: "noodle", name: "Hongdae Kalguksu", type: "Noodles · 9 min walk", status: "risk", label: "Caution", icon: "!", food: "🍜", x: "15%", y: "69%", menus: ["Kalguksu", "Dumplings", "Kimchi"], note: "Shellfish may be used in the broth.", address: "157, Yanghwa-ro, Mapo-gu, Seoul", image: "Kalguksu" },
];
const topKFood = [
  { id: "bibimbap", restaurantId: "gyeong", name: "Vegetable bibimbap", ingredients: "Rice · spinach · carrot · zucchini · egg", checks: ["Egg", "Soy"], emoji: "🥗", tone: "green" },
  { id: "bulgogi", restaurantId: "gyeong", name: "Bulgogi", ingredients: "Marinated beef · onion · soy sauce · sesame", checks: ["Beef", "Soy"], emoji: "🥩", tone: "rose" },
  { id: "japchae", restaurantId: "gyeong", name: "Japchae", ingredients: "Glass noodles · vegetables · soy sauce · sesame", checks: ["Soy"], emoji: "🍜", tone: "orange" },
  { id: "sundubu", restaurantId: "dubu", name: "Mushroom sundubu", ingredients: "Soft tofu · mushroom · zucchini · broth", checks: ["Shellfish", "Soy"], emoji: "🍲", tone: "orange" },
  { id: "samgyeopsal", restaurantId: "bbq", name: "Pork belly with lettuce", ingredients: "Pork belly · lettuce · rice · dipping sauce", checks: ["Pork", "Soy"], emoji: "🥓", tone: "rose" },
  { id: "kimbap", restaurantId: "gyeong", name: "Vegetable kimbap", ingredients: "Rice · seaweed · vegetables · egg", checks: ["Egg"], emoji: "🍙", tone: "green" },
  { id: "tteokbokki", restaurantId: "noodle", name: "Tteokbokki", ingredients: "Rice cakes · chili paste · fish cake", checks: ["Fish", "Wheat", "Soy"], emoji: "🌶️", tone: "rose" },
  { id: "dakgalbi", restaurantId: "bbq", name: "Dakgalbi", ingredients: "Chicken · cabbage · chili paste · rice cake", checks: ["Soy"], emoji: "🍗", tone: "orange" },
  { id: "naengmyeon", restaurantId: "noodle", name: "Naengmyeon", ingredients: "Buckwheat noodles · beef broth · egg", checks: ["Beef", "Egg", "Wheat"], emoji: "🍜", tone: "green" },
  { id: "kimchi", restaurantId: "dubu", name: "Kimchi stew", ingredients: "Kimchi · tofu · pork · broth", checks: ["Pork", "Shellfish", "Soy"], emoji: "🥘", tone: "rose" },
];

function App() {
  const [selectedId, setSelectedId] = useState("gyeong");
  const [profile, setProfile] = useState([]);
  const [saved, setSaved] = useState([]);
  const [, setIsSignedIn] = useState(false);
  const [modal, setModal] = useState("welcome");
  const [authMode, setAuthMode] = useState("signup");
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("en");
  const [area, setArea] = useState("Hongdae, Seoul");
  const [, setPendingArea] = useState("Hongdae, Seoul");
  const [customArea, setCustomArea] = useState("");
  const [view, setView] = useState(() => ({ "/map": "map", "/restaurants": "list" }[window.location.pathname] || "recommendations"));
  const [showQuestion, setShowQuestion] = useState(false);
  const [toast, setToast] = useState("");
  const selected = useMemo(() => restaurants.find((item) => item.id === selectedId), [selectedId]);
  const recommendedMenus = useMemo(() => {
    const suitable = topKFood.filter((item) => !item.checks.some((ingredient) => profile.includes(ingredient)));
    return (suitable.length >= 5 ? suitable : topKFood).slice(0, 5);
  }, [profile]);

  useEffect(() => {
    const localProfile = JSON.parse(localStorage.getItem("kfood-profile") || "[]");
    const localSaved = JSON.parse(localStorage.getItem("kfood-saved") || "[]");
    const hasSession = localStorage.getItem("kfood-session") === "active";
    setProfile(localProfile); setSaved(localSaved); setLanguage(localStorage.getItem("kfood-language") || "en"); setIsSignedIn(hasSession);
    if (hasSession) setModal("");
  }, []);
  useEffect(() => { localStorage.setItem("kfood-profile", JSON.stringify(profile)); }, [profile]);
  useEffect(() => { localStorage.setItem("kfood-saved", JSON.stringify(saved)); }, [saved]);
  useEffect(() => { localStorage.setItem("kfood-language", language); }, [language]);
  useEffect(() => { if (!toast) return undefined; const timer = setTimeout(() => setToast(""), 2600); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => { const path = view === "map" ? "/map" : view === "list" ? "/restaurants" : view === "detail" ? `/restaurants/${selectedId}` : "/for-you"; if (window.location.pathname !== path) window.history.pushState({}, "", path); }, [view, selectedId]);
  useEffect(() => { const onPopState = () => { const path = window.location.pathname; setView(path === "/map" ? "map" : path.startsWith("/restaurants/") ? "detail" : path === "/restaurants" ? "list" : "recommendations"); }; window.addEventListener("popstate", onPopState); return () => window.removeEventListener("popstate", onPopState); }, []);

  const toggleAllergy = (item) => setProfile((now) => now.includes(item) ? now.filter((allergy) => allergy !== item) : [...now, item]);
  const openRestaurant = (id) => { setSelectedId(id); setView("detail"); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const toggleSaved = () => { const isSaved = saved.includes(selected.id); setSaved((now) => isSaved ? now.filter((id) => id !== selected.id) : [...now, selected.id]); setToast(isSaved ? "Removed from saved places." : `${selected.name} has been saved.`); };
  const finishProfile = () => { if (authMode === "signup" && !profile.length) { setToast("Please select at least one allergy or dietary restriction."); return; } localStorage.setItem("kfood-session", "active"); setIsSignedIn(true); setModal(""); setView("recommendations"); setToast(authMode === "signin" ? (profile.length ? "Welcome back. Your saved food profile has been loaded." : "Welcome back. Add your food profile when you are ready.") : "Your food profile is saved. Here are some menu ideas."); };
  const useCurrentLocation = () => {
    if (!navigator.geolocation) { setToast("Location is not supported in this browser. Please enter an area instead."); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => { const location = `Current location · ${coords.latitude.toFixed(3)}, ${coords.longitude.toFixed(3)}`; setArea(location); setModal(""); setToast("Your current GPS location has been applied."); },
      () => setToast("We could not access your location. Please allow location permission or enter an area."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };
  const addCustomArea = () => { const value = customArea.trim(); if (!value) return; setArea(value); setCustomArea(""); setModal(""); setToast(`Area changed to ${value}.`); };

  return <main className="app-shell">
    <nav className="topbar">
      <a className="brand" href="#top"><span className="brand-mark">K</span><span>K-Food Map</span></a>
      <div className="nav-links"><button className={view === "recommendations" ? "active" : ""} onClick={() => setView("recommendations")}>🍽️ For you</button><button className={view === "map" ? "active" : ""} onClick={() => setView("map")}>🗺️ Explore map</button><button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>🍴 Restaurants</button><button onClick={() => setModal("profile")}>My profile</button></div>
      <button className="avatar" onClick={() => setModal("profile")}>{name ? name[0].toUpperCase() : "Me"}</button>
    </nav>

    {view === "recommendations" && <section className="hero-section" id="top"><div className="eyebrow"><span></span> Your personal Korean food map</div><h1>Korean food,<br /><em>made safer for you.</em></h1><p>Add your allergies and dietary needs to discover Korean restaurants and menus that fit the way you eat.</p><div className="location-row"><span className="location-icon">⌖</span><strong>{area}</strong><button onClick={() => {setPendingArea(area);setModal("area");}}>Change area <span>→</span></button></div></section>}

    <section className={`map-layout page-section ${view === "map" ? "" : "view-hidden"}`} id="map"><aside className="side-panel"><div className="panel-heading"><div><p className="overline">My profile</p><h2>Ingredients to avoid</h2></div><button className="edit-button" onClick={() => setModal("profile")}>Edit</button></div><p className="panel-copy">Your selections shape the map and menu recommendations.</p><div className="filter-list">{profile.length ? profile.map((item) => <button key={item} className="filter-chip on" onClick={() => toggleAllergy(item)}><span>◌</span>{item}<b>×</b></button>) : <p className="empty-profile">No dietary information added yet.</p>}</div><button className="add-preference" onClick={() => setModal("profile")}>+ Add allergies or dietary needs</button><div className="legend"><p className="overline">Map guide</p><div><i className="dot great"></i> Good match <small>enough menu information</small></div><div><i className="dot check"></i> Check first <small>some details are missing</small></div><div><i className="dot risk"></i> Caution <small>likely allergen conflict</small></div></div></aside>
      <div className="map-area"><div className="map-toolbar"><button className="area-button" onClick={() => {setPendingArea(area);setModal("area");}}><span>⌖</span> {area} <b>⌄</b></button><button className="map-control" onClick={() => setToast(`Your location is set to ${area}.`)}>◎</button></div><div className="city-map"><div className="river"></div><div className="road road-one"></div><div className="road road-two"></div><div className="road road-three"></div><span className="map-label hongik">Hongik University</span><span className="map-label seogyo">Seogyo-dong</span><span className="map-label yeonnam">Yeonnam-dong</span>{restaurants.map((item) => <div key={item.id} className="map-pin-wrap" style={{left:item.x,top:item.y}}><button className={`map-pin ${item.status} ${selectedId === item.id ? "selected" : ""}`} onClick={() => openRestaurant(item.id)} aria-label={`View ${item.name}`}>{item.food}</button><span><b>{item.menus[0]}</b>{item.name}</span></div>)}<div className="you-are-here"><span></span> You are here</div></div><div className="map-message"><span>✦</span> This map changes with your food profile.</div><button className="next-step" onClick={() => setView("list")}>See restaurants in a list →</button></div></section>

    <section className={`results-section page-section ${view === "recommendations" ? "home-dashboard" : ""} ${view === "recommendations" || view === "list" ? "" : "view-hidden"}`}>
      <div className="results-top"><div><p className="overline">{view === "recommendations" ? "K-Food top 10 · personalized for you" : "Korean restaurants nearby"}</p><h2>{view === "recommendations" ? "Korean food ideas for you" : "Picked for you"}</h2>{view === "recommendations" && <div className="applied-profile"><span>Based on your profile</span>{profile.length ? profile.map((item) => <b key={item}>◌ {item}</b>) : <button onClick={() => setModal("profile")}>Add allergy information</button>}</div>}</div>{view === "list" && <button className="see-all" onClick={() => setView("map")}>Explore map <span>→</span></button>}</div>
<div className={`restaurant-grid ${view === "recommendations" ? "menu-idea-grid" : ""}`}>{view === "recommendations" ? recommendedMenus.map((idea) => <button className={`menu-idea-card ${idea.tone}`} key={idea.id} onClick={() => openRestaurant(idea.restaurantId)}><div className="dish-image"><span>{idea.emoji}</span></div><div className="dish-copy"><h3>{idea.name}</h3><p>{idea.ingredients}</p></div><span className="chevron">→</span></button>) : restaurants.map((item) => <button className={`restaurant-card ${selectedId===item.id ? "current" : ""}`} key={item.id} onClick={() => openRestaurant(item.id)}><div className={`status-icon ${item.status}`}>{item.food}</div><div className="restaurant-main"><div className="restaurant-title"><h3>{item.name}</h3><span className={`status-pill ${item.status}`}>{item.label}</span></div><p>{item.type}</p><div className="menu-tags">{item.menus.slice(0,2).map((menu) => <span key={menu}>{menu}</span>)}</div></div><span className="chevron">→</span></button>)}</div>
      {view === "recommendations" && <section className="home-saved"><div className="saved-heading"><div><p className="overline">Saved list</p><h2>Keep your safe picks close</h2></div></div>{saved.length ? <div className="saved-home-grid">{restaurants.filter((item) => saved.includes(item.id)).map((item) => <button key={item.id} onClick={() => openRestaurant(item.id)}><span className={`status-icon ${item.status}`}>{item.icon}</span><span><b>{item.name}</b><small>{item.menus[0]}</small></span><i>→</i></button>)}</div> : <div className="saved-home-empty">No saved places yet. Open a restaurant and tap the heart to save it here.</div>}</section>}
    </section>

    <section className={`detail-section page-section ${view === "detail" ? "" : "view-hidden"}`} id="restaurant-detail"><div className="detail-intro"><button className="back-button" onClick={() => setView("list")}>← Back to restaurants</button><p className="overline">Restaurant and menu details</p><h2>{selected.name}</h2><p>{selected.type}</p><p className="address">⌖ {selected.address}</p><button className={`heart-button ${saved.includes(selected.id) ? "saved" : ""}`} onClick={toggleSaved} aria-label={saved.includes(selected.id) ? "Remove from saved" : "Save restaurant"}>{saved.includes(selected.id) ? "♥" : "♡"}<span>{saved.includes(selected.id) ? "Saved" : "Save restaurant"}</span></button></div><div className="detail-card"><div className="detail-status"><span className={`status-icon ${selected.status}`}>{selected.icon}</span><div><span className={`status-pill ${selected.status}`}>{selected.label}</span><h3>{selected.note}</h3></div></div><div className="detail-content"><div><p className="overline">Menu ideas for you</p>{selected.menus.map((menu,index) => <div className="menu-row" key={menu}><span className={index === 0 ? "checkmark" : "soft-check"}>{index === 0 ? "✓" : "·"}</span><strong>{menu}</strong><small>{index === 0 ? "Verified details" : "Ask about sauce"}</small><button className="tiny-save" onClick={() => setToast(`${menu} has been saved.`)}>Save</button></div>)}</div><div className="insight"><p className="overline">K-food ingredient insight</p><p><b>{selected.image}</b> recipes can vary between restaurants, especially broth, sauces, and salted seafood. We separate confirmed details from common cooking patterns.</p><button onClick={() => setShowQuestion(!showQuestion)}>{showQuestion ? "Hide Korean question" : "Show Korean question"} <span>→</span></button>{showQuestion && <div className="korean-question"><b>Show this to staff</b><br />이 음식의 육수나 양념에 새우, 조개, 멸치가 들어가나요?</div>}</div></div></div></section>
    <footer><div className="brand"><span className="brand-mark">K</span><span>K-Food Map</span></div><p>Explore Korean food for your needs.</p><span>Please confirm allergen information with staff on site.</span></footer>
    <nav className="mobile-nav" aria-label="Mobile navigation"><button className={view === "recommendations" ? "active" : ""} onClick={() => {setView("recommendations");window.scrollTo({top:0,behavior:"smooth"});}}><span>✦</span>For you</button><button className={view === "map" ? "active" : ""} onClick={() => {setView("map");window.scrollTo({top:0,behavior:"smooth"});}}><span>⌖</span>Map</button><button className={view === "list" ? "active" : ""} onClick={() => {setView("list");window.scrollTo({top:0,behavior:"smooth"});}}><span>☷</span>Places</button><button onClick={() => setModal("profile")}><span>☺</span>Profile</button></nav>
    {toast && <div className="toast">✓ {toast}</div>}
    {modal && <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget && modal !== "welcome") setModal(""); }}><div className="modal" role="dialog" aria-modal="true"><button className="modal-close" onClick={() => modal === "welcome" ? null : setModal("")}>×</button>{modal === "welcome" && <><span className="modal-kicker">WELCOME TO K-FOOD MAP</span><h2>{authMode === "signup" ? <>Create your account<br />and food profile.</> : <>Welcome back.</>}</h2><p>{authMode === "signup" ? "Start with your account details, then add what you need to avoid." : "Sign in to continue with your saved allergies, dietary preferences, and places."}</p><div className="auth-tabs"><button className={authMode === "signup" ? "on" : ""} onClick={() => setAuthMode("signup")}>Sign up</button><button className={authMode === "signin" ? "on" : ""} onClick={() => setAuthMode("signin")}>Sign in</button></div>{authMode === "signup" && <label className="name-input">Name or nickname<input placeholder="e.g. Alice" value={name} onChange={(e) => setName(e.target.value)} /></label>}<label className="name-input">Email address<input type="email" placeholder="alice@example.com" /></label><label className="name-input">Password<input type="password" placeholder="At least 8 characters" /></label>{authMode === "signup" ? <AllergyEditor profile={profile} onToggle={toggleAllergy}/> : <div className="sign-in-profile"><span>✓</span><div><b>Food profile ready</b><p>{profile.length ? `${profile.join(", ")} will be applied after sign in.` : "Your saved allergies and dietary preferences will be loaded."}</p></div></div>}<button className="primary-button" onClick={finishProfile}>{authMode === "signup" ? "Create account and continue" : "Sign in and load my profile"} →</button></>}{modal === "area" && <><span className="modal-kicker">CHOOSE AN AREA</span><h2>Where would you<br />like to eat?</h2><p>Use your phone or browser location, choose a neighborhood, or add your own destination.</p><button className="gps-button" onClick={useCurrentLocation}>⌖ Use my current location</button><div className="custom-area"><input value={customArea} onChange={(event) => setCustomArea(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addCustomArea(); }} placeholder="Enter a neighborhood or address" /><button onClick={addCustomArea} disabled={!customArea.trim()}>Add</button></div><div className="area-options">{["Hongdae, Seoul", "Myeongdong, Seoul", "Jongno, Seoul", "Gangnam, Seoul", "Itaewon, Seoul"].map((item) => <button className={area === item ? "selected" : ""} key={item} onClick={() => {setArea(item);setModal("");setToast(`Area changed to ${item}.`);}}>{item}<span>→</span></button>)}</div></>}{modal === "profile" && <><span className="modal-kicker">MY PROFILE</span><h2>Update your food<br />preferences.</h2><p>Your map and recommendations update as soon as you save.</p><label className="language-select">Display language<select value={language} onChange={(event) => { setLanguage(event.target.value); setToast(event.target.value === "en" ? "Display language set to English." : "Korean is selected. More languages are coming soon."); }}><option value="en">English</option><option value="ko">한국어 (coming soon)</option><option disabled>日本語 (coming soon)</option><option disabled>中文 (coming soon)</option><option disabled>Español (coming soon)</option></select></label><AllergyEditor profile={profile} onToggle={toggleAllergy}/><button className="primary-button" onClick={() => {setModal("");setToast("Your food profile has been updated.");}}>Save changes →</button></>}{modal === "saved" && <><span className="modal-kicker">SAVED PLACES</span><h2>Restaurants and menus<br />to revisit.</h2>{saved.length ? <div className="saved-list">{restaurants.filter((item) => saved.includes(item.id)).map((item) => <button key={item.id} onClick={() => {setSelectedId(item.id);setModal("");setView("detail");}}><span className={`status-icon ${item.status}`}>{item.icon}</span><span><b>{item.name}</b><small>{item.menus[0]} · {item.type}</small></span><i>→</i></button>)}</div> : <div className="saved-empty">You have no saved restaurants yet.<br />Tap the heart on a restaurant you like.</div>}</>}</div></div>}
  </main>;
}

function AllergyEditor({ profile, onToggle }) {
  const [customAllergy, setCustomAllergy] = useState("");
  const addCustomAllergy = () => {
    const value = customAllergy.trim();
    if (value && !profile.includes(value)) onToggle(value);
    setCustomAllergy("");
  };
  return <div className="allergy-editor"><p>Select allergies or dietary restrictions</p><div>{[...allergyOptions, ...profile.filter((item) => !allergyOptions.includes(item))].map((item) => <button key={item} className={profile.includes(item) ? "selected" : ""} onClick={() => onToggle(item)}>{profile.includes(item) ? "✓ " : "+ "}{item}</button>)}</div><div className="custom-allergy"><input value={customAllergy} onChange={(event) => setCustomAllergy(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addCustomAllergy(); } }} placeholder="Add your own (e.g. sesame, peach)" aria-label="Add a custom allergy" /><button onClick={addCustomAllergy} disabled={!customAllergy.trim()}>Add</button></div></div>;
}
export default App;
