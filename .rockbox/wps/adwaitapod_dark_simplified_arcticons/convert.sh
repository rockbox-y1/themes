for f in *.bmp; do
  magick "$f" -type TrueColor -define bmp:format=bmp3 "$f"
done

