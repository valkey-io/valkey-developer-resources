package com.flicenjoyer.ui;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Logger;
import java.util.regex.Pattern;
import javafx.geometry.Pos;
import javafx.scene.layout.StackPane;
import javafx.scene.paint.Color;
import javafx.scene.shape.Rectangle;
import javafx.scene.shape.SVGPath;
import javafx.scene.shape.StrokeLineCap;
import javafx.scene.shape.StrokeLineJoin;

/** Loads SVG icon files from resources and renders them as JavaFX nodes. */
public class IconLoader {

  private static final Logger LOG = Logger.getLogger(IconLoader.class.getName());
  private static final Color BG_COLOR = Color.web("#e08030");
  private static final Pattern PATH_D = Pattern.compile("d=\"([^\"]+)\"");
  private static final Pattern FILLED = Pattern.compile("data-filled=\"(true|false)\"");

  private record IconDef(String path, boolean filled) {}

  private static final Map<String, IconDef> ICONS = new HashMap<>();

  private static final String[] ICON_NAMES = {
    "restart",
    "rewind",
    "play",
    "pause",
    "forward",
    "stop",
    "start-over",
    "back",
    "nav-search",
    "nav-browse",
    "nav-upload",
    "nav-history",
    "nav-reports",
    "nav-bench",
    "nav-admin",
    "edit",
    "delete",
    "check",
    "alert",
    "x-circle"
  };

  static {
    for (var name : ICON_NAMES) {
      try (var is = IconLoader.class.getResourceAsStream("/icons/" + name + ".svg")) {
        IconDef iconDef = generateIconDefinition(is);
        if (iconDef == null) continue;
        ICONS.put(name, iconDef);
      } catch (IOException ex) {
        LOG.warning("[icons] Failed to load " + name + ".svg: " + ex.getMessage());
      }
    }
    LOG.fine("[icons] Loaded " + ICONS.size() + " icons from SVG files");
  }

  private static IconDef generateIconDefinition(InputStream is) throws IOException {
    if (is == null) return null;
    var svg = new String(is.readAllBytes(), StandardCharsets.UTF_8);
    var dm = PATH_D.matcher(svg);
    if (!dm.find()) return null;
    var fm = FILLED.matcher(svg);
    var filled = fm.find() && "true".equals(fm.group(1));
    return new IconDef(dm.group(1), filled);
  }

  /** Icons specifically for the player view. */
  public static StackPane playerIcon(String name) {
    return playerIcon(name, 32);
  }

  /** Icons specifically for the player view. */
  public static StackPane playerIcon(String name, int size) {
    var stack = new StackPane();
    stack.setPrefSize(size, size);
    stack.setMinSize(size, size);
    stack.setMaxSize(size, size);

    var bg = new Rectangle(size, size);
    bg.setArcWidth(8);
    bg.setArcHeight(8);
    bg.setFill(BG_COLOR);

    var def = ICONS.get(name);
    if (def != null) {
      var svg = makeSvgPath(def, Color.WHITE);
      svg.setStrokeWidth(1.8);
      stack.getChildren().addAll(bg, svg);
      StackPane.setAlignment(svg, Pos.CENTER);
    } else {
      stack.getChildren().add(bg);
    }
    return stack;
  }

  /** Renders an icon without background — just the SVG path. */
  public static SVGPath plainIcon(String name, int size, Color color) {
    var def = ICONS.get(name);
    if (def == null) return new SVGPath();
    var svg = makeSvgPath(def, color);
    svg.setStrokeWidth(2.0);
    return svg;
  }

  private static SVGPath makeSvgPath(IconDef def, Color color) {
    var svg = new SVGPath();
    svg.setContent(def.path());
    svg.setFill(def.filled() ? color : Color.TRANSPARENT);
    svg.setStroke(color);
    svg.setStrokeLineCap(StrokeLineCap.ROUND);
    svg.setStrokeLineJoin(StrokeLineJoin.ROUND);
    return svg;
  }
}
