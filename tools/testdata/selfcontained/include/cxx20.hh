#pragma once
#include <concepts>

template <std::integral T>
T twice(T v) { return v + v; }
