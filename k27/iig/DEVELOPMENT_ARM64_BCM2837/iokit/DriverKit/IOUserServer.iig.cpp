/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IOUserServer.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IOUserServer.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IOUserServer.h>

/* @iig implementation */
#include <IOKit/IOUserServer.h>
/* @iig end */


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IOUserServer_Create_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSString * bundleID;
#if !defined(__LP64__)
    uint32_t __bundleIDPad;
#endif /* !defined(__LP64__) */
    const char *  name;
#if !defined(__LP64__)
    uint32_t __namePad;
#endif /* !defined(__LP64__) */
    char __name[64];
    uint64_t  tag;
    uint64_t  options;
};
#pragma pack(4)
struct IOUserServer_Create_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_ool_descriptor_t  bundleID__descriptor;
};
struct IOUserServer_Create_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_ool_descriptor_t  bundleID__descriptor;
    IOUserServer_Create_Msg_Content content;
};
#pragma pack()
#define IOUserServer_Create_Msg_ObjRefs (2)

struct IOUserServer_Create_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  server;
};
#pragma pack(4)
struct IOUserServer_Create_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t server__descriptor;
};
struct IOUserServer_Create_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t server__descriptor;
    IOUserServer_Create_Rpl_Content content;
};
#pragma pack()
#define IOUserServer_Create_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserServer_Create_Msg * message;
#else /* KERNEL */
        const struct IOUserServer_Create_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserServer_Create_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserServer_Create_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserServer_Create_Invocation;
struct IOUserServer_Panic_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    const char *  reason;
#if !defined(__LP64__)
    uint32_t __reasonPad;
#endif /* !defined(__LP64__) */
    char __reason[1024];
};
#pragma pack(4)
struct IOUserServer_Panic_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOUserServer_Panic_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOUserServer_Panic_Msg_Content content;
};
#pragma pack()
#define IOUserServer_Panic_Msg_ObjRefs (1)

struct IOUserServer_Panic_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOUserServer_Panic_Rpl
{
    IORPCMessageMach           mach;
};
struct IOUserServer_Panic_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOUserServer_Panic_Rpl_Content content;
};
#pragma pack()
#define IOUserServer_Panic_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserServer_Panic_Msg * message;
#else /* KERNEL */
        const struct IOUserServer_Panic_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserServer_Panic_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserServer_Panic_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserServer_Panic_Invocation;
struct IOUserServer_Exit_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    const char *  reason;
#if !defined(__LP64__)
    uint32_t __reasonPad;
#endif /* !defined(__LP64__) */
    char __reason[1024];
};
#pragma pack(4)
struct IOUserServer_Exit_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOUserServer_Exit_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOUserServer_Exit_Msg_Content content;
};
#pragma pack()
#define IOUserServer_Exit_Msg_ObjRefs (1)

struct IOUserServer_Exit_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOUserServer_Exit_Rpl
{
    IORPCMessageMach           mach;
};
struct IOUserServer_Exit_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOUserServer_Exit_Rpl_Content content;
};
#pragma pack()
#define IOUserServer_Exit_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserServer_Exit_Msg * message;
#else /* KERNEL */
        const struct IOUserServer_Exit_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserServer_Exit_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserServer_Exit_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserServer_Exit_Invocation;
struct IOUserServer_LoadModule_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    const char *  path;
#if !defined(__LP64__)
    uint32_t __pathPad;
#endif /* !defined(__LP64__) */
    char __path[1024];
};
#pragma pack(4)
struct IOUserServer_LoadModule_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOUserServer_LoadModule_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOUserServer_LoadModule_Msg_Content content;
};
#pragma pack()
#define IOUserServer_LoadModule_Msg_ObjRefs (1)

struct IOUserServer_LoadModule_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOUserServer_LoadModule_Rpl
{
    IORPCMessageMach           mach;
};
struct IOUserServer_LoadModule_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOUserServer_LoadModule_Rpl_Content content;
};
#pragma pack()
#define IOUserServer_LoadModule_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserServer_LoadModule_Msg * message;
#else /* KERNEL */
        const struct IOUserServer_LoadModule_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserServer_LoadModule_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserServer_LoadModule_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserServer_LoadModule_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gIODispatchQueueMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gIOMemoryDescriptorMetaClass;
extern OSMetaClass * gIOBufferMemoryDescriptorMetaClass;
extern OSMetaClass * gIOUserClientMetaClass;
extern OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;
#endif /* !KERNEL */

#if !KERNEL

#define IOUserServer_QueueNames  ""

#define IOUserServer_MethodNames  ""

#define IOUserServerMetaClass_MethodNames  ""

struct OSClassDescription_IOUserServer_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IOUserServer_QueueNames)];
    char               methodNames[sizeof(IOUserServer_MethodNames)];
    char               metaMethodNames[sizeof(IOUserServerMetaClass_MethodNames)];
};

const struct OSClassDescription_IOUserServer_t
OSClassDescription_IOUserServer =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IOUserServer_t),
        .name                    = "IOUserServer",
        .superName               = "IOService",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IOUserServer_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IOUserServer_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IOUserServer_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IOUserServer_t, queueNames),
        .methodNamesSize         = sizeof(IOUserServer_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IOUserServer_t, methodNames),
        .metaMethodNamesSize     = sizeof(IOUserServerMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IOUserServer_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IOUserServer_QueueNames,
    .methodNames     = IOUserServer_MethodNames,
    .metaMethodNames = IOUserServerMetaClass_MethodNames,
};

OSMetaClass * gIOUserServerMetaClass;

static kern_return_t
IOUserServer_New(OSMetaClass * instance);

const OSClassLoadInformation
IOUserServer_Class = 
{
    .description       = &OSClassDescription_IOUserServer.base,
    .metaPointer       = &gIOUserServerMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IOUserServer),

    .resv2             = {0},

    .New               = &IOUserServer_New,
    .resv3             = {0},

};

extern const void * const
gIOUserServer_Declaration;
const void * const
gIOUserServer_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IOUserServer_Class;

static kern_return_t
IOUserServer_New(OSMetaClass * instance)
{
    if (!new(instance) IOUserServerMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IOUserServerMetaClass::New(OSObject * instance)
{
    if (!new(instance) IOUserServer) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IOUserServer::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IOUserServer::_Dispatch(IOUserServer * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IOUserServer_Panic_ID:
        {
            ret = IOUserServer::Panic_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserServer::Panic_Handler, *self, &IOUserServer::Panic_Impl));
            break;
        }
#endif /* !KERNEL */
        case IOUserServer_Exit_ID:
        {
            ret = IOUserServer::Exit_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserServer::Exit_Handler, *self, &IOUserServer::Exit_Impl));
            break;
        }
        case IOUserServer_LoadModule_ID:
        {
            ret = IOUserServer::LoadModule_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserServer::LoadModule_Handler, *self, &IOUserServer::LoadModule_Impl));
            break;
        }
#if KERNEL
        case IOService_RegisterService_ID:
        {
            ret = IOService::RegisterService_Invoke(rpc, self, SimpleMemberFunctionCast(IOService::RegisterService_Handler, *self, &IOUserServer::RegisterService_Impl));
            break;
        }
#endif /* !KERNEL */

        default:
            ret = IOService::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
IOUserServer::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IOUserServerMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IOUserServer_Create_ID:
            ret = IOUserServer::Create_Invoke(rpc, &IOUserServer::Create_Impl);
            break;
#endif /* !KERNEL */

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

kern_return_t
IOUserServer::Create(
        const char * name,
        uint64_t tag,
        uint64_t options,
        OSString * bundleID,
        IOUserServer ** server)
{
    kern_return_t ret;
    union
    {
        IOUserServer_Create_Msg_With_Content msg;
        struct
        {
            IOUserServer_Create_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserServer_Create_Msg_With_Content * msg = &buf.msg;
    struct IOUserServer_Create_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserServer_Create_ID;
    msg->content.__object = (OSObjectRef) OSTypeID(IOUserServer);
    msg->content.__hdr.objectRefs = IOUserServer_Create_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.name = NULL;

    strlcpy(&msg->content.__name[0], name, sizeof(msg->content.__name));

    msg->content.tag = tag;

    msg->content.options = options;

    msg->bundleID__descriptor.type = MACH_MSG_OOL_DESCRIPTOR;
    msg->bundleID__descriptor.copy = MACH_MSG_VIRTUAL_COPY;
    msg->bundleID__descriptor.address = (void *) __builtin_offsetof(IOUserServer_Create_Msg_Content, bundleID);
    msg->content.bundleID = bundleID;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    ret = OSMTypeID(IOUserServer)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserServer_Create_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOUserServer_Create_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *server = OSDynamicCast(IOUserServer, (OSObject *) rpl->content.server);
        if (rpl->content.server && !*server) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOUserServer::Panic(
        const char * reason,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserServer_Panic_Msg_With_Content msg;
        struct
        {
            IOUserServer_Panic_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserServer_Panic_Msg_With_Content * msg = &buf.msg;
    struct IOUserServer_Panic_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserServer_Panic_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserServer_Panic_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.reason = NULL;

    strlcpy(&msg->content.__reason[0], reason, sizeof(msg->content.__reason));

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserServer_Panic_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOUserServer_Panic_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IOUserServer::Exit(
        const char * reason,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserServer_Exit_Msg_With_Content msg;
        struct
        {
            IOUserServer_Exit_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserServer_Exit_Msg_With_Content * msg = &buf.msg;
    struct IOUserServer_Exit_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserServer_Exit_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserServer_Exit_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.reason = NULL;

    strlcpy(&msg->content.__reason[0], reason, sizeof(msg->content.__reason));

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserServer_Exit_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOUserServer_Exit_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IOUserServer::LoadModule(
        const char * path,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserServer_LoadModule_Msg_With_Content msg;
        struct
        {
            IOUserServer_LoadModule_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserServer_LoadModule_Msg_With_Content * msg = &buf.msg;
    struct IOUserServer_LoadModule_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserServer_LoadModule_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserServer_LoadModule_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.path = NULL;

    strlcpy(&msg->content.__path[0], path, sizeof(msg->content.__path));

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserServer_LoadModule_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOUserServer_LoadModule_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IOUserServer::Create_Invoke(const IORPC _rpc,
        Create_Handler func)
{
    IOUserServer_Create_Invocation rpc = { _rpc };
    IOUserServer_Create_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserServer_Create_Msg *         message = rpc.message;
    const IOUserServer_Create_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserServer_Create_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserServer_Create_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserServer_Create_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (((OSObject *) MESSAGE_CONTENT(bundleID)) != NULL && OSDynamicCast(OSString, (OSObject *) MESSAGE_CONTENT(bundleID)) == NULL) { return kIOReturnBadArgument; } 
    if (strnlen(&MESSAGE_CONTENT(__name[0]), sizeof(MESSAGE_CONTENT(__name))) >= sizeof(MESSAGE_CONTENT(__name))) return kIOReturnBadArgument;

    ret = (*func)(        &MESSAGE_CONTENT(__name[0]),
        MESSAGE_CONTENT(tag),
        MESSAGE_CONTENT(options),
        MESSAGE_CONTENT(bundleID),
        (IOUserServer **)&reply->content.server);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserServer_Create_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOUserServer_Create_Rpl_ObjRefs;
    reply->server__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IOUserServer::Panic_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        Panic_Handler func)
{
    IOUserServer_Panic_Invocation rpc = { _rpc };
    IOUserServer_Panic_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserServer_Panic_Msg *         message = rpc.message;
    const IOUserServer_Panic_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserServer_Panic_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserServer_Panic_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserServer_Panic_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (strnlen(&MESSAGE_CONTENT(__reason[0]), sizeof(MESSAGE_CONTENT(__reason))) >= sizeof(MESSAGE_CONTENT(__reason))) return kIOReturnBadArgument;

    ret = (*func)(target,
        &MESSAGE_CONTENT(__reason[0]));

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserServer_Panic_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOUserServer_Panic_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOUserServer::Exit_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        Exit_Handler func)
{
    IOUserServer_Exit_Invocation rpc = { _rpc };
    IOUserServer_Exit_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserServer_Exit_Msg *         message = rpc.message;
    const IOUserServer_Exit_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserServer_Exit_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserServer_Exit_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserServer_Exit_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (strnlen(&MESSAGE_CONTENT(__reason[0]), sizeof(MESSAGE_CONTENT(__reason))) >= sizeof(MESSAGE_CONTENT(__reason))) return kIOReturnBadArgument;

    ret = (*func)(target,
        &MESSAGE_CONTENT(__reason[0]));

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserServer_Exit_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOUserServer_Exit_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOUserServer::LoadModule_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        LoadModule_Handler func)
{
    IOUserServer_LoadModule_Invocation rpc = { _rpc };
    IOUserServer_LoadModule_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserServer_LoadModule_Msg *         message = rpc.message;
    const IOUserServer_LoadModule_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserServer_LoadModule_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserServer_LoadModule_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserServer_LoadModule_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (strnlen(&MESSAGE_CONTENT(__path[0]), sizeof(MESSAGE_CONTENT(__path))) >= sizeof(MESSAGE_CONTENT(__path))) return kIOReturnBadArgument;

    ret = (*func)(target,
        &MESSAGE_CONTENT(__path[0]));

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserServer_LoadModule_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOUserServer_LoadModule_Rpl_ObjRefs;

    return (ret);
}



