/**
 * Format a product_type TAG value (e.g. "COFFEE_TABLE") into title case ("Coffee Table").
 */
export function formatProductType(type) {
  if (!type) return "";
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\B\w+/g, (w) => w.toLowerCase());
}

/**
 * Star rating component using Material Symbols.
 * Renders 5 stars with full-fill for rating >= star index.
 */
export function StarRating({ rating, size = 14, gap = 2 }) {
  return (
    <div style={{ display: "flex", gap, alignItems: "center" }}>
      {[1, 2, 3, 4, 5].map((s) => (
        <span
          key={s}
          className="material-symbols-outlined"
          style={{
            fontSize: size,
            color: "#8a5100",
            fontVariationSettings: `'FILL' ${rating >= s ? 1 : 0}`,
          }}
        >
          star
        </span>
      ))}
    </div>
  );
}

/** Shared category definitions for search TAG filters (sourced from the ABO dataset during ingestion). */
export const SEARCH_CATEGORIES = [
  { label: "Furniture", tags: "CHAIR,SOFA,COUCH,TABLE,DESK,BED,CABINET,OTTOMAN,BENCH,BEAN_BAG_CHAIR,STOOL_SEATING,HOME_FURNITURE_AND_DECOR,FURNITURE,SHELF,HEADBOARD,DRESSER,BED_FRAME,CHEST_OF_DRAWERS,WARDROBE,VANITY,NIGHTSTAND,BOOKCASE,SHELVING,COFFEE_TABLE,DINING_TABLE,END_TABLE" },
  { label: "Lighting", tags: "LAMP,FLOOR_LAMP,TABLE_LAMP,LIGHT_FIXTURE,LIGHT_BULB,STRING_LIGHT,HOME_LIGHTING_AND_LAMPS,HOME_LIGHTING_ACCESSORY" },
  { label: "Textiles", tags: "RUG,CURTAIN,PILLOW,THROW_PILLOW,CUSHION,BLANKET,THROW_BLANKET,FLAT_SHEET,HOME_BED_AND_BATH,WINDOW_SHADE,TOWEL_HOLDER,MATTRESS" },
  { label: "Decor", tags: "WALL_ART,HOME_MIRROR,MIRROR,PLANTER,VASE,CANDLE,CLOCK,CANDLE_HOLDER,PICTURE_FRAME,BASKET" },
  { label: "Sports", tags: "SHOES,SPORTING_GOODS,RECREATION_BALL,EXERCISE_MAT,BACKPACK,EXERCISE_BAND,TECHNICAL_SPORT_SHOE" },
  { label: "Electronics", tags: "HEADPHONES,SPEAKERS,KEYBOARDS,INPUT_MOUSE,MICROPHONE,CHARGING_ADAPTER,BATTERY,COMPUTER_ADD_ON,COMPUTER_COMPONENT,ELECTRONIC_ADAPTER,OFFICE_ELECTRONICS,CONSUMER_ELECTRONICS,SCREEN_PROTECTOR" },
];
