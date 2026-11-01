#pragma once

// Uses std::vector without including <vector>: fails alone.
inline int needs_vector() { return static_cast<int>(std::vector<int>{1}.size()); }
