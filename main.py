from androguard.misc import AnalyzeAPK
from shutil import copyfile
import os
import sys


def copy(source: str, target: str) -> None:
    path = os.path.join(os.getcwd(), 'filter')
    folder = os.path.exists(path)
    if not folder:  # 判断是否存在文件夹如果不存在则创建为文件夹
        os.makedirs(path)
    try:
        copyfile(source, target)
    except IOError as e:
        print("Unable to copy file. %s" % e)
        exit(1)
    except:
        print("Unexpected error:", sys.exc_info())
        exit(1)


def check_by_string(a, d, dx) -> bool:
    screenshot_str = ["screenshot", "screen_shot", "screen-shot", "screen shot", "screencapture", "screen_capture",
                      "screen-capture", "screen capture", "screencap", "screen_cap", "screen-cap", "screen cap"]
    for str in screenshot_str:
        try:
            if dx.strings[str]:
                print(a.get_app_name(), 'have screenshot Suspect with string: ', str)
                return True
        except:
            pass
    return False


def check_by_permission(a, d, dx) -> bool:
    permissions = a.get_permissions()
    for permission in permissions:
        if 'READ_EXTERNAL_STORAGE' in permission:
            print(a.get_app_name(), '有READ_EXTERNAL_STORAGE权限申请')
            return True
    return False


def check_by_CONTENT_URI(a, d, dx) -> bool:
    class_list = dx.get_classes()
    for class_item in class_list:
        class_name = class_item.name
        methods = class_item.get_methods()  # get all methods
        for method in methods:
            m = method.get_method()
            if method.is_external():
                continue
            for ins in m.get_instructions():
                if 'Landroid/provider/MediaStore$Images$Media;->INTERNAL_CONTENT_URI' in ins.get_output() or 'Landroid/provider/MediaStore$Images$Media;->EXTERNAL_CONTENT_URI' in ins.get_output():
                    print(a.get_app_name(), ' ', class_name, ': ', ins.get_output())
                    return True
    return False


'''
根据是否有类（假设为C）继承Android.database.ContentObserver， 并改写onChange方法
然后C被调用，调用的方法里有同时用到 C的构造方法 以及 媒体数据库的URl
'''


def check_overrde_ContentObserver_and_invoke(a, d, dx) -> bool:
    classes = dx.get_classes()
    sum_arrest = False
    for _class in classes:
        # if 'MediaContentObserver' in _class.name:
        has_screenshot_suspicion = False
        arrest = False
        for method in _class.get_methods():
            # 重写了 父类的 Android.database.ContentObserver.onChange 方法， 该方法在父类啥都不做
            # 如果有改写onchange方法，那说明有使用的嫌疑，那么我们就找哪里调用了这个类
            if 'onChange(Z)V' in str(method.get_method()):
                print(_class.name, '继承了Android.database.ContentObserver，并改写了onChange方法，有截屏监控的嫌疑')
                has_screenshot_suspicion = True
            if has_screenshot_suspicion:
                break
        if has_screenshot_suspicion:
            # 看看哪里调用了这个类的<init>方法，然后
            for method in _class.get_methods():
                if '<init>' in str(method.get_method()):
                    for _, call, _ in method.get_xref_from():
                        print("  called by -> {} -- {}".format(call.class_name, call.name))
                        #                         print(dx.classes[call.class_name].get_methods)
                        for target_method in dx.classes[call.class_name].get_methods():
                            if target_method.is_external():
                                continue
                            m = target_method.get_method()
                            use_CONTENT_URI = False
                            has_constructed_ContentObserver = False
                            for ins in m.get_instructions():
                                # problem: 如何知道 这个 ContentObserver 接了 CONTENT_URI， 我目前只能根据方法内是否同时调用
                                # ContentObserver的构造方法 和 是否有用到 ..CONTENT_URI 来判断，希望以后有更好的方法
                                if 'Landroid/provider/MediaStore$Images$Media;->INTERNAL_CONTENT_URI' in ins.get_output() or 'Landroid/provider/MediaStore$Images$Media;->EXTERNAL_CONTENT_URI' in ins.get_output():
                                    use_CONTENT_URI = True
                                # Lcn/sharesdk/demo/utils/ScreenShotListenManager$MediaContentObserver;
                                if _class.name + '-><init>' in ins.get_output():
                                    has_constructed_ContentObserver = True
                                if use_CONTENT_URI and has_constructed_ContentObserver:
                                    print(target_method.name, '同时构造ContentObserver 和 使用媒体数据连接， 所以有嫌疑！')
                                    # 逮捕！！！
                                    arrest = True
                                    break
            if arrest:
                sum_arrest = True
                print(_class.name, '同时构造ContentObserver 和 使用媒体数据连接， 有嫌疑！逮捕！')
            else:
                print(_class.name, '检测完毕！无嫌疑！')
            print('\n')
    if sum_arrest:
        return True
    return False


'''
根据：
1、是否有READ_EXTERNAL_STORAGE权限
2、根据是否使用到CONTENT_URI系列的URL
来判断
'''


def check_by_per_url(apk_path) -> bool:
    a, d, dx = AnalyzeAPK(os.path.join(file_path, apk_name))
    # check media_content
    has_use_media_content = check_by_CONTENT_URI(a, d, dx)
    # check permission
    has_READ_EXTERNAL_STORAGE_permission = check_by_permission(a, d, dx)
    if has_use_media_content and has_READ_EXTERNAL_STORAGE_permission:
        print(a.get_app_name(), ' has screen suspicion')
        return True
    return False


'''
根据：
1、是否有READ_EXTERNAL_STORAGE权限
2、根据是否有类（假设为C）继承Android.database.ContentObserver， 并改写onChange方法
3、然后C被调用，调用的方法里有同时用到 C的构造方法 以及 媒体数据库的URl(目前我只会根据这个方法来判断，其实我觉得应该是吧url传参进C才比较准确，
   然而，不知怎么操作，就这样子先把)
来判断
'''


# check_permission_and_overrde_ContentObserver_and_invoke
def check_p_a_o(apk_path) -> bool:
    a, d, dx = AnalyzeAPK(os.path.join(file_path, apk_name))
    # check permission
    has_READ_EXTERNAL_STORAGE_permission = check_by_permission(a, d, dx)
    # check overrde_ContentObserver_and_invoke
    has_overrde_ContentObserver_and_invoke = check_overrde_ContentObserver_and_invoke(a, d, dx)
    if has_overrde_ContentObserver_and_invoke and has_READ_EXTERNAL_STORAGE_permission:
        print(a.get_app_name(), ' has screen suspicion')
        return True
    return False


if __name__ == '__main__':
    file_path = os.path.join('H:\\share')
    # file_path = os.path.join(os.getcwd(), 'test')
    apk_list = os.listdir(file_path)
    for apk_name in apk_list:
        print('analyzing ', apk_name, '........')
        source = os.path.join(file_path, apk_name)
        target = os.path.join(os.getcwd(), 'filter', apk_name)
        try:
            if check_p_a_o(source):
                copy(source, target)
        except BaseException:
            print(apk_name, '检测失败, err:', BaseException)
        finally:
            pass
