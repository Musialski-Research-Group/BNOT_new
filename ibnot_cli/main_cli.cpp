#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

#include "scene.h"

namespace {

struct CliOptions
{
    std::string image_path;
    std::string points_path;
    std::string output_path;
    std::string stats_path;
    std::string weight_solver = "newton";
    unsigned num_sites = 0;
    unsigned seed = 0;
    unsigned max_iters = 500;
    unsigned max_weight_iters = 500;
    unsigned render_width = 0;
    unsigned render_height = 0;
    double step_x = 0.0;
    double step_w = 0.0;
    double epsilon = 1.0;
    double point_radius = 0.002;
    bool invert = false;
    bool timer = false;
};

void print_usage(const char* argv0)
{
    std::cerr
        << "Usage: " << argv0 << " --image density.pgm --output result.dat [options]\n"
        << "Options:\n"
        << "  --points init.dat              Load initial points instead of sampling from the image\n"
        << "  --num-sites N                  Number of sites for image-adapted random init\n"
        << "  --seed N                       RNG seed (default: 0)\n"
        << "  --invert                       Invert the grayscale density image\n"
        << "  --step-x VALUE                 Position step size, 0 uses line search (default)\n"
        << "  --step-w VALUE                 Weight step size, 0 uses line search (default)\n"
        << "  --epsilon VALUE                Optimization tolerance scale (default: 1.0)\n"
        << "  --max-iters N                  Max outer iterations (default: 500)\n"
        << "  --max-newton-iters N           Max inner weight iterations (default: 500)\n"
        << "  --render-width N               EPS render width in pixels/points (default: 512)\n"
        << "  --render-height N              EPS render height in pixels/points (default: derived from aspect)\n"
        << "  --point-radius VALUE           EPS point radius in normalized coordinates (default: 0.002)\n"
        << "  --weight-solver newton|gd      Weight optimizer backend (default: newton)\n"
        << "  --stats path.txt               Optional stats report path\n"
        << "  --timer                        Enable per-stage timing logs\n";
}

bool require_value(int argc, char** argv, int& index, std::string& value)
{
    if (index + 1 >= argc) return false;
    value = argv[++index];
    return true;
}

unsigned parse_unsigned(const std::string& text, const char* flag)
{
    try
    {
        size_t consumed = 0;
        unsigned long value = std::stoul(text, &consumed);
        if (consumed != text.size()) throw std::invalid_argument("trailing");
        return static_cast<unsigned>(value);
    }
    catch (const std::exception&)
    {
        throw std::runtime_error(std::string("invalid value for ") + flag + ": " + text);
    }
}

double parse_double(const std::string& text, const char* flag)
{
    try
    {
        size_t consumed = 0;
        double value = std::stod(text, &consumed);
        if (consumed != text.size()) throw std::invalid_argument("trailing");
        return value;
    }
    catch (const std::exception&)
    {
        throw std::runtime_error(std::string("invalid value for ") + flag + ": " + text);
    }
}

CliOptions parse_args(int argc, char** argv)
{
    CliOptions options;

    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        std::string value;

        if (arg == "--image")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--image expects a value");
            options.image_path = value;
        }
        else if (arg == "--points")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--points expects a value");
            options.points_path = value;
        }
        else if (arg == "--output")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--output expects a value");
            options.output_path = value;
        }
        else if (arg == "--stats")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--stats expects a value");
            options.stats_path = value;
        }
        else if (arg == "--weight-solver")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--weight-solver expects a value");
            options.weight_solver = value;
        }
        else if (arg == "--num-sites")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--num-sites expects a value");
            options.num_sites = parse_unsigned(value, "--num-sites");
        }
        else if (arg == "--seed")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--seed expects a value");
            options.seed = parse_unsigned(value, "--seed");
        }
        else if (arg == "--max-iters")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--max-iters expects a value");
            options.max_iters = parse_unsigned(value, "--max-iters");
        }
        else if (arg == "--max-newton-iters")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--max-newton-iters expects a value");
            options.max_weight_iters = parse_unsigned(value, "--max-newton-iters");
        }
        else if (arg == "--render-width")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--render-width expects a value");
            options.render_width = parse_unsigned(value, "--render-width");
        }
        else if (arg == "--render-height")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--render-height expects a value");
            options.render_height = parse_unsigned(value, "--render-height");
        }
        else if (arg == "--step-x")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--step-x expects a value");
            options.step_x = parse_double(value, "--step-x");
        }
        else if (arg == "--step-w")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--step-w expects a value");
            options.step_w = parse_double(value, "--step-w");
        }
        else if (arg == "--epsilon")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--epsilon expects a value");
            options.epsilon = parse_double(value, "--epsilon");
        }
        else if (arg == "--point-radius")
        {
            if (!require_value(argc, argv, i, value)) throw std::runtime_error("--point-radius expects a value");
            options.point_radius = parse_double(value, "--point-radius");
        }
        else if (arg == "--invert")
        {
            options.invert = true;
        }
        else if (arg == "--timer")
        {
            options.timer = true;
        }
        else if (arg == "--help" || arg == "-h")
        {
            print_usage(argv[0]);
            std::exit(0);
        }
        else
        {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }

    if (options.image_path.empty()) throw std::runtime_error("--image is required");
    if (options.output_path.empty()) throw std::runtime_error("--output is required");
    if (options.points_path.empty() && options.num_sites == 0)
        throw std::runtime_error("provide either --points or --num-sites");
    if (!options.points_path.empty() && options.num_sites != 0)
        throw std::runtime_error("use only one of --points or --num-sites");
    if (options.weight_solver != "newton" && options.weight_solver != "gd")
        throw std::runtime_error("--weight-solver must be one of: newton, gd");
    if (options.point_radius <= 0.0)
        throw std::runtime_error("--point-radius must be positive");

    return options;
}

std::string build_stats_report(const CliOptions& options,
                               const Scene& scene,
                               unsigned iters,
                               FT energy)
{
    FT mean_abs = 0.0;
    FT max_abs = 0.0;
    FT rms_abs = 0.0;
    scene.compute_capacity_error_stats(mean_abs, max_abs, rms_abs);

    FT mean_capacity = scene.compute_mean_capacity();
    FT mean_rel = (mean_capacity > 0.0) ? (mean_abs / mean_capacity) : 0.0;
    FT max_rel = (mean_capacity > 0.0) ? (max_abs / mean_capacity) : 0.0;
    FT rms_rel = (mean_capacity > 0.0) ? (rms_abs / mean_capacity) : 0.0;

    std::ostringstream report;
    report << std::setprecision(16);
    report << "image_path: " << options.image_path << '\n';
    report << "output_path: " << options.output_path << '\n';
    if (!options.points_path.empty()) report << "points_path: " << options.points_path << '\n';
    if (!options.stats_path.empty()) report << "stats_path: " << options.stats_path << '\n';
    report << "weight_solver: " << options.weight_solver << '\n';
    report << "seed: " << options.seed << '\n';
    report << "render_width: " << scene.get_render_width() << '\n';
    report << "render_height: " << scene.get_render_height() << '\n';
    report << "point_radius: " << scene.get_render_point_radius() << '\n';
    report << "visible_sites: " << scene.count_visible_sites() << '\n';
    report << "iterations: " << iters << '\n';
    report << "energy: " << energy << '\n';
    report << "mean_capacity: " << mean_capacity << '\n';
    report << "mean_abs_capacity_error: " << mean_abs << '\n';
    report << "max_abs_capacity_error: " << max_abs << '\n';
    report << "rms_abs_capacity_error: " << rms_abs << '\n';
    report << "mean_rel_capacity_error: " << mean_rel << '\n';
    report << "max_rel_capacity_error: " << max_rel << '\n';
    report << "rms_rel_capacity_error: " << rms_rel << '\n';
    return report.str();
}

} // namespace

int main(int argc, char** argv)
{
    try
    {
        CliOptions options = parse_args(argc, argv);

        Scene scene;
        std::srand(options.seed);
        if (options.timer) scene.toggle_timer();
        scene.set_render_width(options.render_width);
        scene.set_render_height(options.render_height);
        scene.set_render_point_radius(options.point_radius);

        scene.load_image(options.image_path);
        if (options.invert) scene.toggle_invert();

        if (!options.points_path.empty()) scene.load_points(options.points_path);
        else scene.generate_random_sites_based_on_image(options.num_sites);

        if (!scene.is_valid()) throw std::runtime_error("scene initialization failed");

        std::ostringstream optimization_log;
        unsigned iters = 0;
        if (options.weight_solver == "newton")
        {
            iters = scene.optimize_all(options.step_w,
                                       options.step_x,
                                       options.max_weight_iters,
                                       options.epsilon,
                                       options.max_iters,
                                       optimization_log);
        }
        else
        {
            iters = scene.optimize_all_gradient_weights(options.step_w,
                                                        options.step_x,
                                                        options.max_weight_iters,
                                                        options.epsilon,
                                                        options.max_iters,
                                                        optimization_log);
        }

        scene.save_points(options.output_path);

        if (!optimization_log.str().empty()) std::cout << optimization_log.str();

        FT energy = scene.compute_wcvt_energy();
        std::string report = build_stats_report(options, scene, iters, energy);
        std::cout << report;

        if (!options.stats_path.empty())
        {
            std::ofstream stats(options.stats_path.c_str());
            if (!stats) throw std::runtime_error("failed to open stats output: " + options.stats_path);
            stats << report;
        }

        return 0;
    }
    catch (const std::exception& ex)
    {
        std::cerr << "ibnot_new_cli error: " << ex.what() << std::endl;
        return 1;
    }
}
