// TEST DATA ONLY: driven energy balance with constant net power, SI units.
#include <cstdlib>
#include <fstream>
#include <string>
int main() {
    const char* output=std::getenv("RESEARCHAUDIT_OUTPUT_DIR");
    if (!output) return 2;
    std::ofstream f(std::string(output)+"/metrics.csv");
    if (!f) return 3;
    f << "time,energy,power\n";
    for (int t=0;t<=10;++t) f << t << ',' << 10+2*t << ",2\n";
    return 0;
}
