#ifndef NESTED_HH
#define NESTED_HH
#include "good.hh"

inline int nested() { return static_cast<int>(good().size()); }
#endif
