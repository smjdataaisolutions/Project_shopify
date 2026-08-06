import { NavLink } from "react-router";
import styles from "./analyticsTopNavigation.module.css";

const NAVIGATION_ITEMS = [
  { label: "Store Performance Overview", to: "/app", end: true },
  { label: "Sales", to: "/app/sales" },
  { label: "Inventory", to: "/app/inventory" },
  { label: "Orders", to: "/app/orders" },
  { label: "Products", to: "/app/products" },
];

export function AnalyticsTopNavigation() {
  return (
    <nav className={styles.navigation} aria-label="Analytics pages">
      <div className={styles.links}>
        {NAVIGATION_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => (
              `${styles.link} ${isActive ? styles.active : ""}`.trim()
            )}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
