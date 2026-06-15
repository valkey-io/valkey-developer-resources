package com.flicenjoyer.ui;

import java.util.function.IntConsumer;
import javafx.scene.layout.HBox;
import javafx.scene.paint.Color;
import javafx.scene.shape.SVGPath;

/**
 * A 5-star rating widget. Filled golden stars represent the rating (0–5). Click a star to set
 * rating, or press 0–5 keys when focused. Zero means "not rated".
 */
public class StarRating extends HBox {

  private static final String STAR_PATH =
      "M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26Z";
  private static final Color GOLD = Color.web("#daa520");
  private static final Color EMPTY = Color.web("#444");

  private int rating;
  private final SVGPath[] stars = new SVGPath[5];
  private IntConsumer onRatingChanged;

  public StarRating() {
    this(0);
  }

  public StarRating(int initialRating) {
    super(4);
    this.rating = Math.max(0, Math.min(5, initialRating));
    setFocusTraversable(true);

    for (int i = 0; i < 5; i++) {
      var star = new SVGPath();
      star.setContent(STAR_PATH);
      star.setStroke(GOLD);
      star.setStrokeWidth(1);
      star.setScaleX(0.7);
      star.setScaleY(0.7);
      star.setCursor(javafx.scene.Cursor.HAND);
      final int starIndex = i + 1;
      star.setOnMouseClicked(e -> setRating(starIndex));
      stars[i] = star;
      getChildren().add(star);
    }

    setOnKeyPressed(
        e -> {
          var code = e.getCode();
          if (code.isDigitKey() && code.getName().length() == 1) {
            var digit = Character.getNumericValue(code.getName().charAt(0));
            if (digit >= 0 && digit <= 5) setRating(digit);
          }
        });

    updateStars();
  }

  public void setRating(int newRating) {
    this.rating = Math.max(0, Math.min(5, newRating));
    updateStars();
    if (onRatingChanged != null) onRatingChanged.accept(rating);
  }

  public int getRating() {
    return rating;
  }

  public void setOnRatingChanged(IntConsumer callback) {
    this.onRatingChanged = callback;
  }

  private void updateStars() {
    for (int i = 0; i < 5; i++) {
      stars[i].setFill(i < rating ? GOLD : EMPTY);
    }
  }
}
