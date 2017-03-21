# J-Rectifier


Here's a repository of the J Rectifier plugin created by Jan Mądrzyk.

J Rectifier is a QGIS plugin, compatible with 2.x versions of QGIS software

----Little bit more about the plugin-----


J Rectifier is the plugin made for people who often georeference raster files using QGIS for that purpose.The tool does exactly the same thing as GDAL Georeferencer does, but presents different workflow which is (in the author’s opinion) more efficient and allows to receive the same results much quicker.

The main difference between the tools is approach to adding Ground Control Points (GCPs). J Rectifier plugin is much more flexible in this subject. When GDAL Georeferencer forces user to pick GCPs in a strict order (first – show the point on the rastere, then – show it on map, or type values), J Rectifier allows to pick points in any order, for example – user can show 10 points on a Map, and then find analogous 10 points on the raster that he/she wants to georeference. Moreover, J Rectifier plugin doesn’t ask user to confirm the coordinates every time he/she pick the point from canvas, what makes georeferencing quicker and lets avoid unnecessary ‘clicking’.

Another feature that makes a great difference between the plugins is auto zooming. After clicking the first from pair of analogical points, the feature moves the view in the other canvas to the area where the next point will probably occur. User doesn’t need to spend time on searching the spot all over the raster.

Jan Mądrzyk
janmadrzyk@gmail.com
https://github.com/JanekWMJ/
